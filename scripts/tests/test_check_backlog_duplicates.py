"""Tests for the backlog-duplicate warning check (FR-118).

`fetch_open_prs` shells out to `gh`, which this sandbox does not have installed (same gap
FR-114 hit — see that script's own test file); it is verified via a workflow_dispatch run
instead (`.github/workflows/check-backlog-duplicates.yml`). Everything else is pure and
tested here against fixed fixtures, including the two near-misses (FR-112/FR-67,
FR-114/#282) that motivated this item.
"""

from check_backlog_duplicates import (
    corpus_common_words,
    find_likely_matches,
    format_report,
    keywords,
    overlap_coefficient,
)

BACKLOG = """# Backlog

## FR-67 · tech-lead · Fix sunrise/sunset formula and ADR-006 stale flag
- state: done
- gated: no
- why: FR-19's sunrise/sunset formula had a known rounding bug; ADR-006 still flags it unresolved
- dod:
  - sunrise/sunset formula corrected and covered by a regression test
  - ADR-006's stale flag removed
  - failure case: a formula fix with no regression test is not accepted

## FR-79 · tech-lead · Crew removal fails when a push subscription exists
- state: ready
- gated: no
- why: removing a crew member with an active push subscription raises a Postgres ForeignKeyViolation
- dod:
  - ON DELETE CASCADE added for push_subscriptions.crew_member_id
  - failure case: removing a crew member with no subscription still works unchanged

## FR-108 · pm · Re-verify FAMU/NSP/Prace.cz/Jobs.cz role and tooling signals
- state: done
- gated: no
- why: FR-22's desk research cites sources that were never read in full or have since changed
- dod:
  - each source re-fetched via the open-egress runner and compared against the original citation
  - failure case: a stale citation is flagged, never silently kept or silently swapped
"""

OPEN_PRS = [
    {
        "number": 282,
        "title": "docs(tech-lead): FR-112 close as duplicate of FR-67, fix stale ADR-006 note",
        "body": "Closes FR-112 as a duplicate of FR-67. FR-19's sunrise/sunset formula was already "
        "fixed; this PR also removes ADR-006's stale flag.",
    },
    {
        "number": 301,
        "title": "fix(backend): patch pyjwt CVEs flagged by FR-110's audit",
        "body": "Bumps PyJWT 2.13.0 to 2.15.1, closing all 13 CVEs pip-audit flagged.",
    },
]


def test_keywords_drops_stopwords_and_short_tokens() -> None:
    kw = keywords("Fix the sunrise and sunset formula for ADR-006")
    assert "sunrise" in kw
    assert "sunset" in kw
    assert "the" not in kw
    assert "and" not in kw
    assert "for" not in kw


def test_overlap_coefficient_identical_sets_is_one() -> None:
    assert overlap_coefficient({"a", "b"}, {"a", "b"}) == 1.0


def test_overlap_coefficient_disjoint_sets_is_zero() -> None:
    assert overlap_coefficient({"a"}, {"b"}) == 0.0


def test_overlap_coefficient_empty_set_is_zero() -> None:
    assert overlap_coefficient(set(), {"a"}) == 0.0


def test_overlap_coefficient_favours_the_smaller_set() -> None:
    """A short candidate fully contained in a long, noisy item scores high even though the
    two sets' sizes are wildly different — the scenario Jaccard would have missed (a
    `done` item's running note can carry hundreds of keywords against a candidate's dozen)."""
    small = {"sunrise", "sunset", "formula"}
    large = small | {f"noise{i}" for i in range(200)}
    assert overlap_coefficient(small, large) == 1.0


def test_fr112_against_fr67_would_have_been_flagged() -> None:
    """FR-112 proposed re-verifying the sunrise/sunset formula FR-67 had already fixed."""
    matches = find_likely_matches(
        "Verify sunrise/sunset formula and ADR-006 flag",
        "ADR-006 still flags the sunrise/sunset formula as needing verification",
        BACKLOG,
    )
    refs = [m.ref for m in matches]
    assert "FR-67" in refs


def test_fr114_against_pr282_would_have_been_flagged() -> None:
    """FR-114's own predecessor concern: a PR already delivering the proposed work."""
    matches = find_likely_matches(
        "Fix stale sunrise/sunset formula note",
        "FR-19's sunrise/sunset formula and ADR-006's stale flag need a fix",
        BACKLOG,
        OPEN_PRS,
    )
    assert any(m.source == "pr" and m.ref == "#282" for m in matches)


def test_unrelated_candidate_finds_nothing() -> None:
    matches = find_likely_matches(
        "Add a crew member birthday reminder",
        "no production currently surfaces a crew member's birthday anywhere",
        BACKLOG,
        OPEN_PRS,
    )
    assert matches == []


def test_corpus_common_words_drops_near_universal_terms() -> None:
    """Words most items share (e.g. this corpus's own "crew"/"production") are too common
    to signal a specific duplicate, the false-positive this item's own calibration against
    the real BACKLOG.md surfaced before this filter existed. Needs enough documents
    (MIN_CORPUS_SIZE_FOR_COMMON_WORDS) for "common" to mean anything."""
    sets = [{"crew", "production", f"unique{i}"} for i in range(12)]
    common = corpus_common_words(sets, fraction=0.5)
    assert "crew" in common
    assert "production" in common
    assert "unique0" not in common


def test_corpus_common_words_empty_input() -> None:
    assert corpus_common_words([]) == set()


def test_corpus_common_words_skips_filtering_below_minimum_size() -> None:
    """A handful of documents can't reliably tell "common" from "this pair happens to
    share a word" apart (see test_fr114_against_pr282_would_have_been_flagged's own
    BACKLOG+OPEN_PRS corpus, which is below the minimum) — so nothing is dropped."""
    sets = [{"crew", "production"}, {"crew", "production"}, {"crew", "production"}]
    assert corpus_common_words(sets, fraction=0.1) == set()


def test_ubiquitous_domain_words_alone_do_not_trigger_a_match() -> None:
    """A candidate sharing only generic, corpus-wide words (crew/production/add, present in
    nearly every item) with several unrelated items should not be flagged — this reproduces
    the false positive this item's own real-BACKLOG.md smoke test caught. Twelve items so
    the corpus clears MIN_CORPUS_SIZE_FOR_COMMON_WORDS, as the real BACKLOG.md does."""
    items = "\n\n".join(
        f"""## FR-{i} · frontend · Item {i} about crew and production work
- state: done
- gated: no
- why: crew members and the production both need this, item {i} specifically
- dod:
  - add something crew- and production-related, item {i}
  - failure case: item {i}'s own edge case is handled"""
        for i in range(1, 13)
    )
    backlog = f"# Backlog\n\n{items}\n"
    matches = find_likely_matches(
        "Add a crew member birthday reminder",
        "no production currently surfaces a crew member's birthday anywhere",
        backlog,
    )
    assert matches == []


def test_ready_item_is_not_a_duplicate_source() -> None:
    """FR-79 is `ready`, not `done`/`in-progress` — not yet delivered or underway, so citing
    the same topic is not itself a duplicate the way FR-112/FR-114 were."""
    matches = find_likely_matches(
        "Push subscription blocks crew removal",
        "a Postgres ForeignKeyViolation is raised when removing a crew member with an active push subscription",
        BACKLOG,
    )
    assert matches == []


def test_matches_are_sorted_highest_score_first() -> None:
    matches = find_likely_matches(
        "Sunrise sunset formula and FAMU source re-verification",
        "both the sunrise/sunset formula fix and the FAMU/NSP/Prace.cz/Jobs.cz re-verification are relevant",
        BACKLOG,
        OPEN_PRS,
    )
    scores = [m.score for m in matches]
    assert scores == sorted(scores, reverse=True)


def test_format_report_no_matches() -> None:
    assert format_report("New idea", []) == "No likely duplicate found for: New idea"


def test_format_report_lists_each_match() -> None:
    from check_backlog_duplicates import Match

    out = format_report("New idea", [Match("backlog", "FR-67", "Fix sunrise formula", 0.5)])
    assert "FR-67" in out
    assert "warning only" in out
