"""FR-115: read FAMU's two production-regulations Office documents from a
runner with open egress, closing FR-108's own named follow-up — a plain HTML
text fetch (`fetch_page_text.py`) cannot read binary `.doc`/`.docx` content,
and this sandbox's proxy blocks `www.famu.cz` outright, so this script only
ever runs from a GitHub Actions runner, never from the routine's own sandbox.

Steps: fetch the production-regulations page HTML, find the `<a href>` for
each named file (case-insensitive substring match on the filename fragment,
resolved against the page URL), download it, then convert to plain text with
whatever tool applies to its extension — `python-docx` for `.docx`, `antiword`
(falling back to `catdoc`) for the legacy binary `.doc` format, since neither
Python nor the stdlib can parse the old OLE-based format directly. Prints
every step's outcome (found the link or not, downloaded or not, converted or
not, then the extracted text) to stdout and $GITHUB_STEP_SUMMARY, so a human
reads the actual regulation text directly rather than trusting a filename
guess — the same "state what's actually there" convention FR-88/89/108 used.

Usage: `python3 scripts/fetch_office_docs.py` (stdlib only for the fetch;
`python-docx` and `antiword`/`catdoc` are expected on PATH for conversion —
the workflow step installs them before this runs).
"""

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from urllib.parse import urljoin

TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (compatible; FilmRunnerResearchBot/1.0; +https://sandovabarbora.github.io/filmrunner/)"
PAGE_URL = "https://www.famu.cz/en/faculty/studio-famu/production-regulations/"

# Substrings that identify each file's link on the page, from FR-108's own
# reading of the page's file-listing block (dated 2 June 2021 / 21 October
# 2025 there).
TARGET_FILES = [
    "RULES FOR PRODUCING EXERCISES",
    "Production Regulations_Radiosrental",
]

_HREF_RE = re.compile(r'<a\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _fetch_bytes(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.status, r.read(20_000_000), ""
    except urllib.error.HTTPError as e:
        return e.code, b"", f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001 — report every failure mode, not just the typed ones
        return 0, b"", f"{type(e).__name__}: {e}"


def _find_links(page_html: str, page_url: str) -> dict[str, str | None]:
    found: dict[str, str | None] = {name: None for name in TARGET_FILES}
    for href, inner in _HREF_RE.findall(page_html):
        label = html.unescape(_TAG_RE.sub(" ", inner)).strip()
        haystack = f"{href} {label}"
        for name in TARGET_FILES:
            if found[name] is None and name.lower() in haystack.lower():
                found[name] = urljoin(page_url, href)
    return found


def _convert_docx(path: str) -> tuple[bool, str]:
    try:
        import docx  # python-docx
    except ImportError:
        return False, "python-docx not installed"
    try:
        doc = docx.Document(path)
        paras = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    paras.append(" | ".join(cells))
        text = "\n".join(paras)
        return (True, text) if text.strip() else (False, "parsed but no extractable text")
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


def _convert_doc(path: str) -> tuple[bool, str]:
    for tool, args in (("antiword", [path]), ("catdoc", [path])):
        exe = shutil.which(tool)
        if not exe:
            continue
        try:
            result = subprocess.run([exe, *args], capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and result.stdout.strip():
                return True, result.stdout
        except Exception as e:  # noqa: BLE001
            return False, f"{tool} failed: {type(e).__name__}: {e}"
    return False, "neither antiword nor catdoc available or both produced no text"


def main(argv: list[str]) -> int:
    report: list[str] = ["# FR-115 FAMU Office document dump", ""]

    status, body, err = _fetch_bytes(PAGE_URL)
    report.append(f"## Page: {PAGE_URL}")
    report.append(f"- status: {status or 'unreachable'}{' — ' + err if err else ''} ({len(body)} bytes)")
    if status != 200:
        report.append("- **failed: could not read the file-listing page, so no links could be resolved**")
        text = "\n".join(report)
        print(text)
        _write_summary(text)
        return 1

    page_html = body.decode("utf-8", errors="replace")
    links = _find_links(page_html, PAGE_URL)

    any_failure = False
    for name, url in links.items():
        report.append("")
        report.append(f"## {name}")
        if url is None:
            report.append("- **failed: no `<a href>` on the page matched this filename** — the page's link text or structure may have changed since FR-108's read")
            any_failure = True
            continue
        report.append(f"- link found: {url}")

        fstatus, fbody, ferr = _fetch_bytes(url)
        report.append(f"- download status: {fstatus or 'unreachable'}{' — ' + ferr if ferr else ''} ({len(fbody)} bytes)")
        if fstatus != 200 or not fbody:
            report.append("- **failed: file did not download**")
            any_failure = True
            continue

        suffix = ".docx" if url.lower().endswith(".docx") else ".doc"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(fbody)
            tmp_path = tmp.name
        try:
            ok, text_or_err = _convert_docx(tmp_path) if suffix == ".docx" else _convert_doc(tmp_path)
        finally:
            os.unlink(tmp_path)

        if not ok:
            report.append(f"- **failed to convert: {text_or_err}**")
            any_failure = True
            continue

        report.append(f"- converted, {len(text_or_err)} characters of text:")
        report.append("")
        report.append("```")
        report.append(text_or_err[:20000])
        report.append("```")

    text = "\n".join(report)
    print(text)
    _write_summary(text)
    return 1 if any_failure else 0


def _write_summary(text: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
