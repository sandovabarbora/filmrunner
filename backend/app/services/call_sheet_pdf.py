"""FR-57: the crew list out of an old call sheet PDF.

Two extractors over the PDF's text layer: a heuristics pass (a phone number
anchors a row; department headers by the same word list the paste import
uses) that needs nothing, and Claude (when the key is set) that reads the
whole page text and returns the same shape. Both return candidates for a
preview; nothing is created here. The PDF is handled in memory only.
"""

from __future__ import annotations

import io
import json
import logging
import re
from dataclasses import dataclass, field

import httpx
from pypdf import PdfReader

from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 60_000  # a call sheet is 1–4 pages; anything bigger is not a call sheet


class NotACallSheetPdf(ValueError):
    """No text layer (a scan), too large, or not a PDF at all."""


@dataclass
class ExtractedContact:
    name: str
    department: str | None = None
    position: str | None = None
    phone: str | None = None
    email: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class Extraction:
    contacts: list[ExtractedContact]
    method: str  # "claude" | "heuristics"
    pages: int
    warnings: list[str] = field(default_factory=list)


def extract_text(data: bytes) -> tuple[str, int]:
    """Text of every page, or NotACallSheetPdf when there is no text layer."""
    if len(data) > MAX_PDF_BYTES:
        raise NotACallSheetPdf("The PDF is over 10 MB; export a lighter one")
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:  # pypdf raises a zoo of errors on non-PDFs
        raise NotACallSheetPdf("That file is not a readable PDF") from exc
    text = "\n".join(pages).strip()
    if len(text) < 40:
        raise NotACallSheetPdf("This PDF has no text layer (a scan or a photo); export the call sheet from the program that made it")
    return text[:MAX_TEXT_CHARS], len(pages)


# ---- heuristics -----------------------------------------------------------------

PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{3,4}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
DEPARTMENTS = ["camera", "electric", "grip", "sound", "art", "costume", "makeup", "make-up", "hair", "production", "direction", "directing",
               "locations", "transport", "catering", "stunts", "vfx", "sfx", "script", "editorial", "post", "lighting", "ad", "assistant directors",
               "kamera", "osvětlovači", "osvetlovaci", "zvuk", "výprava", "vyprava", "kostýmy", "kostymy", "masky", "produkce", "režie", "rezie",
               "lokace", "doprava", "stavba", "rekvizity", "catering", "grip"]
WORD_RE = re.compile(r"[^\W\d_][\w'’-]*")  # regex ranges like [Á-Ž] mix cases in Unicode; case is checked in Python instead
STOP_WORDS = re.compile(r"\b(nemocnice|hospital|policie|police|hasiči|lokace|location|adresa|address|catering|parking|parkování|sraz|call)\b", re.I)


def _looks_like_department(line: str) -> bool:
    l = line.strip().rstrip(":").lower()
    return l in DEPARTMENTS or any(l.endswith(f" {d}") or l.startswith(f"{d} ") for d in DEPARTMENTS)


JOB_WORDS = {
    "gaffer", "grip", "dop", "dp", "kameraman", "kameramanka", "producer", "producent", "producentka", "director", "režisér", "reziser",
    "režisérka", "asistent", "asistentka", "assistant", "koordinátor", "koordinator", "coordinator", "driver", "řidič", "ridic", "vedoucí",
    "vedouci", "mistr", "supervisor", "manager", "manažer", "operator", "operátor", "electrician", "osvětlovač", "osvetlovac", "sound", "zvukař",
    "zvukar", "makeup", "maskér", "masker", "costume", "kostymér", "kostymer", "runner", "editor", "loader", "focus", "puller", "scripty",
    "skript", "continuity", "location", "lokační", "catering", "nurse", "medic", "zdravotník", "stunt", "kaskadér", "casting", "hlavní", "hlavni",
    "best", "boy", "key", "swing", "dolly", "crane", "steadicam", "drone", "pilot", "unit", "upm", "line", "post", "vfx", "sfx", "animal", "wrangler",
}


def _unglue(line: str) -> str:
    """pypdf often concatenates table cells: "Eva Dvořáková1. asistent+420 …" → put the spaces back.
    Case-aware for Czech letters; a lower→upper split needs a lowercase run of 3+ so "DoP" and "McDonald" survive,
    and a digit→letter split only before an uppercase letter so "1st" survives."""
    out: list[str] = []
    prev = ""
    lower_run = 0
    for ch in line:
        split = False
        if prev:
            if (ch.isupper() or ch.isdigit() or ch in "+(") and (prev == "." or (prev.islower() and lower_run >= 3)):
                split = True
            elif prev.isdigit() and ch.isupper():
                split = True
        if split:
            out.append(" ")
        out.append(ch)
        lower_run = lower_run + 1 if ch.islower() else 0
        prev = ch
    return " ".join("".join(out).split())


def _name_word(word: str) -> bool:
    return len(word) > 1 and word[0].isupper() and word[1:].islower() and word.lower() not in JOB_WORDS


def _find_name(before: str) -> tuple[str, str] | None:
    """The first two consecutive capitalised non-job words are the name; everything else is the position."""
    words = before.split()
    for i in range(len(words) - 1):
        if _name_word(words[i]) and _name_word(words[i + 1]):
            name = f"{words[i]} {words[i + 1]}"
            rest = " ".join(words[:i] + words[i + 2 :]).strip(" -–|:,")
            return name, rest
    return None


def heuristics(text: str) -> list[ExtractedContact]:
    """A line with a phone number is a person: the first "Firstname Lastname" before the number is the name,
    whatever else stands before the number is the position; a bare department word above sets the department.
    Lines about hospitals, locations and the like are skipped. Good enough for the common table layouts."""
    out: list[ExtractedContact] = []
    department: str | None = None
    for raw in text.splitlines():
        line = _unglue(raw)
        if not line:
            continue
        if _looks_like_department(line) and not PHONE_RE.search(line):
            department = line.rstrip(":").strip()
            continue
        phone_m = PHONE_RE.search(line)
        if not phone_m or len(re.sub(r"\D", "", phone_m.group(0))) < 9:
            continue
        before = line[: phone_m.start()]
        email_m = EMAIL_RE.search(line)
        if email_m and email_m.start() < phone_m.start():
            before = line[: email_m.start()]
        if STOP_WORDS.search(before):
            continue
        found = _find_name(before)
        if not found:
            continue
        name, rest = found
        out.append(ExtractedContact(name=name, department=department, position=rest or None,
                                    phone=phone_m.group(0).strip(), email=email_m.group(0) if email_m else None))
    return out


# ---- Claude ---------------------------------------------------------------------

PROMPT = """You are reading the text of a film call sheet (Czech or English). Extract every crew and cast contact you can find.
Return ONLY a JSON object of the form {"contacts": [{"name": "...", "department": "...", "position": "...", "phone": "...", "email": "..."}]}.
Rules: name is the person's full name as written; department is the crew department heading the person sits under (Czech or English, as written; null if unknown);
position is their job title (null if unknown); phone as written (null if none); email (null if none). Do not invent people or numbers.
Skip company names, hospitals, addresses and locations. If there is nothing usable, return {"contacts": []}.

CALL SHEET TEXT:
"""


def claude(text: str, *, api_key: str, model: str, client: httpx.Client | None = None) -> list[ExtractedContact]:
    """Structured extraction by Claude; raises on transport or shape errors so the caller can fall back."""
    http = client or httpx.Client(timeout=60)
    resp = http.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": model, "max_tokens": 4096, "temperature": 0,
              "messages": [{"role": "user", "content": PROMPT + text}]},
    )
    resp.raise_for_status()
    body = resp.json()
    content = "".join(block.get("text", "") for block in body.get("content", []) if block.get("type") == "text")
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise ValueError("no JSON in the model's answer")
    data = json.loads(match.group(0))
    out: list[ExtractedContact] = []
    for c in data.get("contacts", []):
        name = str(c.get("name") or "").strip()
        if not name:
            continue
        out.append(ExtractedContact(name=name, department=(c.get("department") or None), position=(c.get("position") or None),
                                    phone=(str(c["phone"]).strip() if c.get("phone") else None), email=(c.get("email") or None)))
    return out


# ---- entry ----------------------------------------------------------------------

def extract_contacts(data: bytes, *, client: httpx.Client | None = None) -> Extraction:
    """Text out of the PDF, then Claude when configured (falling back to heuristics on any failure), else heuristics."""
    text, pages = extract_text(data)
    settings = get_settings()
    warnings: list[str] = []
    contacts: list[ExtractedContact] = []
    method = "heuristics"
    if settings.anthropic_api_key:
        try:
            contacts = claude(text, api_key=settings.anthropic_api_key, model=settings.anthropic_model, client=client)
            method = "claude"
        except Exception as exc:  # noqa: BLE001 — any failure means "use the dumb path", never a 500
            logger.warning("Claude extraction failed (%s); using heuristics", exc.__class__.__name__)
            warnings.append("The smart extraction was unavailable; this is the plain-text pass, check the rows")
    if method == "heuristics":
        contacts = heuristics(text)
    for c in contacts:
        digits = re.sub(r"\D", "", c.phone or "")
        if c.phone and len(digits) < 9:
            c.warnings.append(f'phone "{c.phone}" does not look like a number')
            c.phone = None
        if not c.position:
            c.warnings.append("no position found")
        if not c.department:
            c.warnings.append("no department found")
    if not contacts:
        warnings.append("No contacts found in the text; if the sheet is a table of images, export it again from the program that made it")
    return Extraction(contacts=contacts, method=method, pages=pages, warnings=warnings)
