"""FR-118: warn before a new backlog proposal duplicates existing work.

FR-112 (duplicate of FR-67) and FR-114 (duplicate of already-delivered PR #282) each cost a
full shift cycle: the pm-fallback step (TEAM.md Shift contract §7) wrote a new BACKLOG.md item,
and only a later shift's manual read of `done`/`in-progress` notes or the open-PR queue caught
that the work already existed or was already underway. This script runs that same check before
the item is written, on the one piece of information a fallback step has before committing
anything: the candidate's own title and `why` line.

It never blocks a proposal — a human (or a future shift) reads the printed likely matches and
decides. Silence ("no likely duplicate found") is itself the useful signal when there genuinely
is none.

Usage:
    python scripts/check_backlog_duplicates.py --title "..." --why "..."

Checks the candidate's keywords against every `done`/`in-progress` item in
docs/company/BACKLOG.md (title + why + dod + note) and every open pull request's title and body
(`gh pr list --json title,body`, the same shape `scripts/pr_merge_report.py`/FR-114 uses).
`gh` is not installed in this sandbox (same gap FR-66/67/68/83/114 hit), so `fetch_open_prs()`
is exercised by a workflow_dispatch run rather than locally; everything else — tokenizing,
scoring, and matching — takes no live `gh` output as a hard dependency and is unit-tested
against fixed fixtures in scripts/tests/test_check_backlog_duplicates.py.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from check_company_docs import parse_items

# Short common words add noise to keyword overlap without signalling similarity; everything
# else (including domain words like "the", "call", "sheet") stays in deliberately — a false
# positive here costs one read, a false negative costs a duplicated shift.
STOPWORDS = {
    "a", "an", "and", "any", "are", "as", "at", "be", "but", "by", "can", "do", "does",
    "for", "from", "has", "have", "if", "in", "into", "is", "it", "its", "no", "not",
    "of", "on", "or", "own", "so", "than", "that", "the", "their", "then", "this", "to",
    "up", "was", "were", "what", "when", "which", "who", "will", "with",
}
_WORD = re.compile(r"[a-z0-9]+")

# A candidate's title+why is a handful of words; a `done`/`in-progress` BACKLOG.md item
# (or a PR body) is often a long running note (FR-116's own entry, picked as a calibration
# fixture, carries 200+ distinct keywords). Jaccard punishes that size mismatch even when
# the candidate's own vocabulary sits almost entirely inside the larger text, so matching
# uses the overlap coefficient (intersection over the *smaller* set) instead.
#
# Below this score, or with too few shared words to rule out coincidence, two texts are not
# worth a human's attention.
MATCH_THRESHOLD = 0.3
MIN_SHARED_KEYWORDS = 3
TOP_N = 5

# A word that shows up in most items (process boilerplate like "failure", "case", "shift",
# or this company's own always-present nouns like "crew", "production") carries no signal
# about which *specific* item is a duplicate — it would otherwise make every candidate that
# mentions "crew" look 30%+ similar to every other crew-related item. Rather than hand-list
# such words (the corpus already changes every shift), any word present in more than this
# fraction of the comparison corpus is dropped before scoring, the same idea as TF-IDF's
# document-frequency discount.
CORPUS_COMMON_FRACTION = 0.25


@dataclass
class Match:
    source: str  # "backlog" or "pr"
    ref: str  # "FR-67" or "#282"
    title: str
    score: float


def keywords(text: str) -> set[str]:
    """Lowercase word set with stopwords and very short tokens dropped."""
    return {w for w in _WORD.findall(text.lower()) if len(w) >= 3 and w not in STOPWORDS}


def overlap_coefficient(a: set[str], b: set[str]) -> float:
    """|A∩B| / min(|A|, |B|): how much of the *smaller* set the larger one contains."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


#  Below this many documents, two items sharing a word (e.g. exactly the pair that *is* a
# real duplicate) can themselves push that word's frequency past CORPUS_COMMON_FRACTION —
# the fraction only tells "common vs. rare" apart once there's enough corpus for a word's
# spread to mean something; the real BACKLOG.md plus open PRs comfortably clears this.
MIN_CORPUS_SIZE_FOR_COMMON_WORDS = 10


def corpus_common_words(keyword_sets: list[set[str]], fraction: float = CORPUS_COMMON_FRACTION) -> set[str]:
    """Words present in more than `fraction` of `keyword_sets` — too common in this corpus
    to signal a duplicate on their own. Returns nothing for a corpus too small to make that
    call (see MIN_CORPUS_SIZE_FOR_COMMON_WORDS)."""
    if len(keyword_sets) < MIN_CORPUS_SIZE_FOR_COMMON_WORDS:
        return set()
    counts: dict[str, int] = {}
    for kw in keyword_sets:
        for word in kw:
            counts[word] = counts.get(word, 0) + 1
    threshold = fraction * len(keyword_sets)
    return {word for word, n in counts.items() if n > threshold}


def backlog_candidates(text: str) -> list[tuple[str, str, set[str]]]:
    """(item_id, title, keywords) for every `done`/`in-progress` BACKLOG.md item.

    A `ready`/`blocked` item is not yet delivered or underway, so it is not a duplicate risk
    the same way — nothing stops a proposal from also naming one, and FR-112/FR-114's own
    near-misses were both against `done`/`in-progress` work.
    """
    out = []
    for item in parse_items(text):
        if not item.item_id.startswith("FR-"):
            continue
        if item.fields.get("state") not in ("done", "in-progress"):
            continue
        blob = " ".join([item.title, item.fields.get("why", ""), item.fields.get("note", ""), *item.dod])
        out.append((item.item_id, item.title, keywords(blob)))
    return out


def pr_candidates(prs: list[dict]) -> list[tuple[str, str, set[str]]]:
    """(ref, title, keywords) for a `gh pr list --json title,body`-shaped list."""
    out = []
    for pr in prs:
        number = pr.get("number")
        title = pr.get("title", "")
        body = pr.get("body") or ""
        ref = f"#{number}" if number is not None else title
        out.append((ref, title, keywords(f"{title} {body}")))
    return out


def find_likely_matches(
    title: str,
    why: str,
    backlog_text: str,
    prs: list[dict] | None = None,
) -> list[Match]:
    """Likely duplicates of a candidate (title, why), highest score first, capped at TOP_N."""
    backlog_items = backlog_candidates(backlog_text)
    pr_items = pr_candidates(prs or [])
    common = corpus_common_words([kw for _, _, kw in backlog_items] + [kw for _, _, kw in pr_items])

    candidate = keywords(f"{title} {why}") - common
    matches: list[Match] = []
    for item_id, item_title, kw in backlog_items:
        kw = kw - common
        score = overlap_coefficient(candidate, kw)
        if score >= MATCH_THRESHOLD and len(candidate & kw) >= MIN_SHARED_KEYWORDS:
            matches.append(Match("backlog", item_id, item_title, score))
    for ref, pr_title, kw in pr_items:
        kw = kw - common
        score = overlap_coefficient(candidate, kw)
        if score >= MATCH_THRESHOLD and len(candidate & kw) >= MIN_SHARED_KEYWORDS:
            matches.append(Match("pr", ref, pr_title, score))
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:TOP_N]


def format_report(title: str, matches: list[Match]) -> str:
    if not matches:
        return f"No likely duplicate found for: {title}"
    lines = [f"Possible duplicates for: {title}", "(warning only — nothing here blocks the proposal)"]
    for m in matches:
        tag = m.ref if m.source == "backlog" else f"PR {m.ref}"
        lines.append(f"  {m.score:.0%}  {tag}  {m.title}")
    return "\n".join(lines)


def fetch_open_prs() -> list[dict]:
    """Shell out to `gh pr list` for every open PR's number, title and body."""
    raw = subprocess.run(
        ["gh", "pr", "list", "--state", "open", "--limit", "200", "--json", "number,title,body"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(raw)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True, help="candidate backlog item title")
    parser.add_argument("--why", required=True, help="candidate backlog item's why line")
    parser.add_argument("--backlog", default="docs/company/BACKLOG.md", type=Path)
    parser.add_argument(
        "--skip-prs",
        action="store_true",
        help="skip the gh pr list check (e.g. gh not installed in this environment)",
    )
    args = parser.parse_args(argv)

    prs: list[dict] = []
    if not args.skip_prs:
        try:
            prs = fetch_open_prs()
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            print(f"warning: could not fetch open PRs ({exc}); checking BACKLOG.md only", file=sys.stderr)

    matches = find_likely_matches(args.title, args.why, args.backlog.read_text(), prs)
    print(format_report(args.title, matches))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
