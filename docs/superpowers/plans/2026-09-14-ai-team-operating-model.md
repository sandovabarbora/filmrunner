# AI Team Operating Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the FilmRunner skeleton into a company repo with a written operating model, a company brain in `docs/company/`, CI gates, and one daily cloud routine that works from the backlog and emails a digest.

**Architecture:** Markdown files in `docs/company/` are the single source of truth; a small Python checker validates their format in CI and before every routine run; a GitHub Actions workflow runs the checker, pytest against a Postgres service and a Playwright smoke test; one cloud routine (`/schedule`) clones the GitHub repo daily, works one backlog item on a branch, commits state files to `main`, and emails a digest.

**Tech Stack:** git + `gh` CLI (account `sandovabarbora`, ssh), GitHub Actions, Python 3.11 (repo target; local machine has 3.14, use `uv venv --python 3.11`), pytest, Playwright (Python), Anthropic cloud routines via `RemoteTrigger`, Artifact DB for the status board.

**Spec:** `docs/superpowers/specs/2026-09-14-ai-team-operating-model-design.md`

## Global Constraints

- Canonical code is this skeleton; `~/Documents/Coding/sandbox/film_production` is reference only and is never modified by this plan.
- Repo lives at `~/Documents/Coding/filmrunner`, remote `sandovabarbora/filmrunner`, private.
- No secrets in git: `.env` stays ignored; only `.env.example` is committed.
- Digest email goes to `sandovabarb@gmail.com` and to no other address.
- Routine: daily 05:00 Europe/Prague, `claude-sonnet-5`, Gmail connector only, at most one backlog item per run.
- Code reaches `main` only via PR with the `ci` check green; the routine commits only `docs/company/STATUS.md`, `INBOX.md`, `LOG.md` directly to `main`.
- Repo docs are written in English; the digest email is written in Czech.
- No em dashes in code or comments (dev-team coding standard).
- Local verification needs Docker Desktop running (Postgres 16 via `docker compose up db`); if it is not running, CI on the first push is the verification and the plan says so.

---

### Task 1: Move the repo, initialise git, create the private GitHub remote

**Files:**
- Move: `~/Downloads/filmrunner` → `~/Documents/Coding/filmrunner` (whole tree)
- Modify: `.gitignore` (add `.venv/` already present; add `frontend/tests/__pycache__/`, `.playwright/`)

**Interfaces:**
- Produces: a git repo at `~/Documents/Coding/filmrunner` on branch `main` with remote `origin` = `git@github.com:sandovabarbora/filmrunner.git`. Every later task assumes this path.

- [ ] **Step 1: Move the directory and confirm nothing was left behind**

```bash
mv ~/Downloads/filmrunner ~/Documents/Coding/filmrunner
ls ~/Downloads/filmrunner 2>&1 | head -1   # expected: No such file or directory
ls ~/Documents/Coding/filmrunner            # expected: backend frontend docs README.md ...
```

- [ ] **Step 2: Initialise git on `main` and make the first commit**

```bash
cd ~/Documents/Coding/filmrunner
git init -b main
git add -A
git status --short | grep -c "" # expected: ~35 files, and NO backend/.env in the list
git commit -m "chore: FilmRunner call-sheet skeleton (backend, offline PWA, tests, design docs)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FBFRX5N8PsXsGvWdB9Y9FU"
```

Expected: one commit; `git ls-files | grep -c "\.env$"` prints `0`.

- [ ] **Step 3: Create the private GitHub repo and push**

```bash
gh repo create sandovabarbora/filmrunner --private --source=. --remote=origin --push \
  --description "FilmRunner: the living call sheet. Company repo: product, code, and the AI team's operating model."
gh repo view sandovabarbora/filmrunner --json visibility,defaultBranchRef -q '.visibility + " " + .defaultBranchRef.name'
```

Expected: `PRIVATE main`.

- [ ] **Step 4: Verify the push**

```bash
git log --oneline origin/main | head -1   # expected: the "chore: FilmRunner call-sheet skeleton" commit
```

---

### Task 2: Company brain (`docs/company/`) with a format checker

**Files:**
- Create: `docs/company/TEAM.md`, `docs/company/BRIEF.md`, `docs/company/DECISIONS.md`, `docs/company/BACKLOG.md`, `docs/company/STATUS.md`, `docs/company/INBOX.md`, `docs/company/LOG.md`
- Create: `scripts/check_company_docs.py`
- Create: `scripts/tests/test_check_company_docs.py`
- Modify: `README.md` (add "How this company runs" section pointing to `docs/company/TEAM.md`)

**Interfaces:**
- Produces: `check_company_docs.main(root: Path) -> int` returning `0` when `BACKLOG.md` and `INBOX.md` parse and all ids are unique and states valid, `1` otherwise, printing one problem per line. CLI: `python scripts/check_company_docs.py [docs/company]`.
- Produces the item grammar the routine and Task 3's CI depend on:
  - Backlog item: a `## FR-<n> · <role> · <title>` heading followed by bullet lines `- state: ready|in-progress|blocked|done`, `- gated: yes|no|partial`, `- why: ...`, `- dod:` with indented `  - ...` lines, at least one of which starts with `failure case:`.
  - Inbox item: a `## #<n> · <role> · <title>` heading followed by `- state: pending|approved|rejected|done`, `- what:`, `- why:`, `- risk:`, `- proposal:`.
  - Roles: `pm`, `tech-lead`, `frontend`, `marketing`, `security`, `qa`.

- [ ] **Step 1: Write the failing tests for the checker**

`scripts/tests/test_check_company_docs.py`:

```python
"""Tests for the company-docs format checker.

The checker is the routine's and CI's guard that BACKLOG.md and INBOX.md
stay machine-readable; these tests pin the grammar so a doc edit that
breaks it fails loudly instead of silently confusing the daily shift.
"""

from pathlib import Path

import pytest

from check_company_docs import ROLES, check_backlog, check_inbox, main

GOOD_BACKLOG = """# Backlog

## FR-1 · pm · BRIEF.md v0
- state: ready
- gated: no
- why: no constitution yet
- dod:
  - BRIEF.md lists open questions
  - failure case: a question with no owner is flagged, not dropped
"""

GOOD_INBOX = """# Inbox

## #1 · marketing · Send interview invitations
- state: pending
- what: email 5 first ADs
- why: discovery
- risk: cold outreach from an unknown sender
- proposal: founder sends from her own address
"""


def test_good_backlog_has_no_problems() -> None:
    assert check_backlog(GOOD_BACKLOG) == []


def test_good_inbox_has_no_problems() -> None:
    assert check_inbox(GOOD_INBOX) == []


def test_duplicate_backlog_id_is_reported() -> None:
    text = GOOD_BACKLOG + GOOD_BACKLOG.split("# Backlog")[1]
    problems = check_backlog(text)
    assert any("duplicate id FR-1" in p for p in problems)


def test_invalid_state_is_reported() -> None:
    text = GOOD_BACKLOG.replace("state: ready", "state: someday")
    problems = check_backlog(text)
    assert any("FR-1: invalid state 'someday'" in p for p in problems)


def test_unknown_role_is_reported() -> None:
    text = GOOD_BACKLOG.replace("· pm ·", "· ceo ·")
    problems = check_backlog(text)
    assert any("FR-1: unknown role 'ceo'" in p for p in problems)
    assert "pm" in ROLES


def test_backlog_item_without_failure_case_is_reported() -> None:
    text = GOOD_BACKLOG.replace("  - failure case: a question with no owner is flagged, not dropped\n", "")
    problems = check_backlog(text)
    assert any("FR-1: dod has no 'failure case:' line" in p for p in problems)


def test_inbox_missing_field_is_reported() -> None:
    text = GOOD_INBOX.replace("- risk: cold outreach from an unknown sender\n", "")
    problems = check_inbox(text)
    assert any("#1: missing field 'risk'" in p for p in problems)


def test_main_returns_nonzero_on_problem(tmp_path: Path) -> None:
    (tmp_path / "BACKLOG.md").write_text(GOOD_BACKLOG.replace("gated: no", "gated: maybe"))
    (tmp_path / "INBOX.md").write_text(GOOD_INBOX)
    assert main(tmp_path) == 1


def test_main_returns_zero_on_clean_docs(tmp_path: Path) -> None:
    (tmp_path / "BACKLOG.md").write_text(GOOD_BACKLOG)
    (tmp_path / "INBOX.md").write_text(GOOD_INBOX)
    assert main(tmp_path) == 0


@pytest.mark.parametrize("filename", ["BACKLOG.md", "INBOX.md"])
def test_real_company_docs_are_valid(filename: str) -> None:
    root = Path(__file__).resolve().parents[2] / "docs" / "company"
    assert (root / filename).exists(), f"{filename} missing from docs/company"
    assert main(root) == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd ~/Documents/Coding/filmrunner
uv venv --python 3.11 backend/.venv && . backend/.venv/bin/activate
pip install -r backend/requirements.txt
python -m pytest scripts/tests -q
```

Expected: FAIL, `ModuleNotFoundError: No module named 'check_company_docs'`.

- [ ] **Step 3: Write the checker**

`scripts/check_company_docs.py`:

```python
"""Validate the machine-readable parts of docs/company.

BACKLOG.md and INBOX.md are read by the daily routine to decide what to
work on and what is approved. This checker keeps their grammar strict so
a typo in a state never silently hides or unlocks work.

Usage:
    python scripts/check_company_docs.py [path/to/docs/company]

Exit code 0 when clean, 1 when any problem is printed.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROLES = {"pm", "tech-lead", "frontend", "marketing", "security", "qa"}
BACKLOG_STATES = {"ready", "in-progress", "blocked", "done"}
GATED_VALUES = {"yes", "no", "partial"}
INBOX_STATES = {"pending", "approved", "rejected", "done"}
INBOX_FIELDS = ("state", "what", "why", "risk", "proposal")

_HEADING = re.compile(r"^## (?P<id>FR-\d+|#\d+) · (?P<role>[a-z-]+) · (?P<title>.+)$")
_FIELD = re.compile(r"^- (?P<key>[a-z]+):\s*(?P<value>.*)$")
_DOD_LINE = re.compile(r"^  - (?P<text>.+)$")


@dataclass
class Item:
    """One `## id · role · title` block and its bullet fields."""

    item_id: str
    role: str
    title: str
    fields: dict[str, str] = field(default_factory=dict)
    dod: list[str] = field(default_factory=list)


def parse_items(text: str) -> list[Item]:
    """Split a company doc into items.

    Args:
        text: Full markdown content of BACKLOG.md or INBOX.md.

    Returns:
        Items in document order; lines before the first heading are ignored.
    """
    items: list[Item] = []
    current: Item | None = None
    in_dod = False
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            current = Item(heading["id"], heading["role"], heading["title"].strip())
            items.append(current)
            in_dod = False
            continue
        if current is None:
            continue
        if in_dod and (dod_line := _DOD_LINE.match(line)):
            current.dod.append(dod_line["text"].strip())
            continue
        in_dod = False
        if bullet := _FIELD.match(line):
            current.fields[bullet["key"]] = bullet["value"].strip()
            in_dod = bullet["key"] == "dod"
    return items


def _common_problems(items: list[Item]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item.item_id in seen:
            problems.append(f"duplicate id {item.item_id}")
        seen.add(item.item_id)
        if item.role not in ROLES:
            problems.append(f"{item.item_id}: unknown role '{item.role}' (allowed: {sorted(ROLES)})")
    return problems


def check_backlog(text: str) -> list[str]:
    """Return problems in BACKLOG.md text; empty list means valid."""
    items = parse_items(text)
    problems = _common_problems(items)
    for item in items:
        state = item.fields.get("state")
        if state not in BACKLOG_STATES:
            problems.append(f"{item.item_id}: invalid state '{state}' (allowed: {sorted(BACKLOG_STATES)})")
        gated = item.fields.get("gated")
        if gated not in GATED_VALUES:
            problems.append(f"{item.item_id}: invalid gated '{gated}' (allowed: {sorted(GATED_VALUES)})")
        if not item.fields.get("why"):
            problems.append(f"{item.item_id}: missing field 'why'")
        if not item.dod:
            problems.append(f"{item.item_id}: missing dod")
        elif not any(line.startswith("failure case:") for line in item.dod):
            problems.append(f"{item.item_id}: dod has no 'failure case:' line")
    return problems


def check_inbox(text: str) -> list[str]:
    """Return problems in INBOX.md text; empty list means valid."""
    items = parse_items(text)
    problems = _common_problems(items)
    for item in items:
        for key in INBOX_FIELDS:
            if not item.fields.get(key):
                problems.append(f"{item.item_id}: missing field '{key}'")
        state = item.fields.get("state")
        if state is not None and state not in INBOX_STATES:
            problems.append(f"{item.item_id}: invalid state '{state}' (allowed: {sorted(INBOX_STATES)})")
    return problems


def main(root: Path) -> int:
    """Check BACKLOG.md and INBOX.md under root; print problems; return exit code."""
    problems = [
        *(f"BACKLOG.md: {p}" for p in check_backlog((root / "BACKLOG.md").read_text())),
        *(f"INBOX.md: {p}" for p in check_inbox((root / "INBOX.md").read_text())),
    ]
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/company")
    sys.exit(main(target))
```

Add `scripts/tests/conftest.py` so the module imports from the tests:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

- [ ] **Step 4: Run the checker tests; expect only the two real-docs tests to fail**

```bash
python -m pytest scripts/tests -q
```

Expected: 9 pass, 2 fail with `BACKLOG.md missing from docs/company` (the real files do not exist yet).

- [ ] **Step 5: Write `docs/company/TEAM.md`**

```markdown
# FilmRunner team: how this company runs

FilmRunner is run by one human founder (Barbora Sandova) and an AI team.
This file is the operating model. Every interactive session and every
cloud routine reads it first. It is written so an agent with zero prior
context can act correctly from it alone.

## Source of truth

`docs/company/` is the company's brain. Nothing outside it is authoritative
about strategy, priorities, or approvals.

| File | Purpose | Who writes it |
|---|---|---|
| `BRIEF.md` | Constitution: thesis, customer, business model, out-of-scope, kill criteria | PM role drafts, founder approves |
| `DECISIONS.md` | Dated decisions with why and revisit-when; append-only | any role; founder confirms |
| `BACKLOG.md` | Prioritised work items (grammar below) | PM proposes, founder orders |
| `STATUS.md` | Latest state per role; overwritten each run | every session and routine |
| `INBOX.md` | Approval queue (grammar below); only the founder changes `state` | roles append; founder decides |
| `LOG.md` | One line per unit of work; append-only | every session and routine |
| `TEAM.md` | This file | founder approves changes |

Reference material, never a source of truth: the June 2026
`PRODUCT_BRIEF.md` and the old codebase in
`~/Documents/Coding/sandbox/film_production` (not in this repo).

## Approval contract

The team may, without asking: read anything; write to this repo on a
branch; open pull requests; write drafts (emails, copy, PRDs, ADRs); do web
research; update `STATUS.md`, `INBOX.md`, `BACKLOG.md`, `LOG.md`.

The team may NOT, unless an `INBOX.md` item for that exact action has
`state: approved`: merge to `main`; send email to anyone other than
`sandovabarb@gmail.com`; spend money; publish anything publicly; create
accounts on any service; change DNS or infrastructure.

Violating this contract is a bug, not initiative. Approved items that
need the founder's own credentials (accounts, payments, sending from her
address to third parties) are executed by the founder in an interactive
session, never by the routine.

`main` receives code only through a pull request with the `ci` check
green. The routine commits exactly three files directly to `main`:
`docs/company/STATUS.md`, `INBOX.md`, `LOG.md` (rebase first, never force).

## Roles

Roles are disciplines the assistant switches into, not separate agents.
Each combines a `dev-team` role file with installed skills. When taking a
task, name the role chosen. Gates (security, qa) run before merges and
report findings in `STATUS.md`; they are not daily reporters.

| Role id | Discipline | Accountable for now |
|---|---|---|
| `pm` | dev-team pm + idea-validation, customer-research, competitive-teardown, pricing | BRIEF.md from scratch; backlog ordering proposals |
| `tech-lead` | dev-team tech-lead, backend-python, dba | architecture, ADRs, review standard, API contract |
| `frontend` | dev-team frontend + impeccable | PWA, offline behaviour, crew-facing call sheet on mobile |
| `marketing` | product-marketing, launch, content-strategy, cold-email | positioning, Prague go-to-market, outreach drafts (gated) |
| `security` (gate) | dev-team security + security-checklist | checklist before every merge |
| `qa` (gate) | dev-team qa, sdet | tests first; every DoD has a failure case |

## Item grammar (checked by `scripts/check_company_docs.py`)

Backlog item:

    ## FR-<n> · <role id> · <title>
    - state: ready | in-progress | blocked | done
    - gated: yes | no | partial
    - why: <one line>
    - dod:
      - <check>
      - failure case: <what must happen when it goes wrong>

Inbox item:

    ## #<n> · <role id> · <title>
    - state: pending | approved | rejected | done
    - what: <the action>
    - why: <the reason>
    - risk: <what could go wrong>
    - proposal: <the recommended way to do it>

Run `python scripts/check_company_docs.py` before committing either file.

## The daily shift (cloud routine)

One routine, daily at 05:00 Europe/Prague, model claude-sonnet-5, clones
this repo from GitHub, Gmail connector only. Its contract:

1. Read `TEAM.md`, `BRIEF.md`, `BACKLOG.md`, `INBOX.md`, `STATUS.md`.
2. Execute `approved` inbox items that are doable inside the repo
   (typically merging a PR) and mark them `done`. Approved items that need
   credentials or money: do not execute; write "waiting for founder,
   manual" in `STATUS.md`.
3. Take the highest `ready` backlog item with `gated: no`. Work in the role
   the item names, to its DoD. Code only on branch `shift/<id>`; tests must
   pass; open a PR. Discovery and marketing outputs are markdown under
   `docs/` on the same branch. Set the item to `in-progress` (or `done`
   when the PR is the whole deliverable and only awaits merge).
4. When something needs approval, append an `INBOX.md` item and continue
   with the next ungated item. Never block.
5. Write `STATUS.md` (per role: summary, tests, blockers, needs_approval)
   and one `LOG.md` line. Commit these three files directly to `main`.
6. Send the digest to `sandovabarb@gmail.com` only, in Czech, five lines
   max: what was done, what awaits approval (#id), what is blocked, PR link.
   On Mondays add a proposed plan for the week.
7. At most one backlog item per run. If nothing is workable, send a one-line
   digest ("nic k práci, backlog potřebuje tebe") and stop.

### Runbook

- Routine list and logs: from an interactive Claude Code session, load
  `RemoteTrigger` and call `list_runs` then `get_run_log` for the run in
  question. A run that was skipped before a session existed leaves no run;
  check the routine itself with `get`.
- Cron is in UTC. 05:00 Prague is 03:00 UTC in summer time and 04:00 UTC in
  winter time; update the cron expression at DST changes (late March, late
  October) or accept a one-hour drift.
- Routine edit/disable: https://claude.ai/code/routines
- If the routine sent email to anyone other than the founder, or pushed
  code to `main`: disable it at the URL above, record the incident in
  `DECISIONS.md`, fix the prompt, re-enable.

## Status board

The "AI Team Status" artifact (four cards: product, engineering, security,
marketing; activity log) is a projection of `STATUS.md` and `LOG.md`. It is
synced from an interactive session with the step "sync board" unless the
routine is verified to have the Artifact tool (see `DECISIONS.md`). The
email digest is always the current channel; the board may lag.
```

- [ ] **Step 6: Write `docs/company/BRIEF.md` (v0: open questions, no conclusions)**

```markdown
# FilmRunner brief (v0, 2026-09-14)

Status: open questions. Nothing here is decided. The June 2026
PRODUCT_BRIEF.md (old repo) is one input among several, not a conclusion.

## Working hypothesis (to be tested, not assumed)

A shoot-day call sheet that is live, offline-honest, and lands in every
crew member's pocket is a wedge into film production software. Owner of
the problem: the person who assembles and distributes call sheets.

## Open questions, each with an owner and how it gets answered

| # | Question | Owner | How we answer it |
|---|---|---|---|
| Q1 | Who actually assembles the call sheet on Czech productions: 1st AD, 2nd AD, production coordinator? Does it differ by production size? | pm | discovery interviews (FR-3) |
| Q2 | What do they use today and what does it cost them in hours per shoot day? | pm | interviews + competitive teardown (FR-2) |
| Q3 | What goes wrong most often (late revisions, wrong call times, no signal on location)? | pm | interviews |
| Q4 | Who pays: the production company, the producer's line item, or the AD personally? At what price does it stop being a no-brainer? | pm | interviews, pricing hypotheses |
| Q5 | Is Prague dense enough for word-of-mouth distribution, or is the first market elsewhere? | marketing | count active productions, talk to film schools |
| Q6 | Which existing tool would we have to displace, and what would make an AD switch mid-season? | pm | teardown (FR-2) |
| Q7 | What is the smallest thing that proves the wedge: a call sheet viewer, a distributor, or a script-to-call-sheet flow? | pm + tech-lead | after Q1 to Q3 |

## Kill criteria (draft)

- Five interviews in Prague and no one names call-sheet distribution as a
  top-three pain: stop and re-frame.
- No plausible payer at any price above the cost of running it: stop.

## Out of scope until this brief is v1

New product features, landing page, pricing page, deployment, outreach
beyond interview invitations.
```

- [ ] **Step 7: Write `docs/company/DECISIONS.md`**

```markdown
# Decisions

Append-only. Format: date, decision, why, revisit when.

## 2026-09-14: canonical code is this skeleton, not the old repo
- Decision: FilmRunner is rebuilt on this repository (FastAPI + SQLAlchemy +
  Alembic + Postgres backend, single-file offline PWA). The old codebase at
  `~/Documents/Coding/sandbox/film_production` (Next.js + FastAPI +
  Supabase, June 2026 brief, studio-readiness work) is reference material.
- Why: founder's explicit choice for a conscious restart around the call
  sheet; the old repo accumulated surface area without a validated wedge.
- Revisit when: BRIEF.md v1 needs a capability the old repo already has and
  this one does not (then port, do not switch).

## 2026-09-14: strategy is founded from scratch
- Decision: the June 2026 PRODUCT_BRIEF.md is an input, not the constitution.
  BRIEF.md starts as open questions answered by discovery.
- Why: founder's call; the earlier thesis was never validated with customers.
- Revisit when: never automatically; BRIEF.md v1 supersedes this note.

## 2026-09-14: company brain lives in the repo as markdown
- Decision: `docs/company/` is the single source of truth; no Notion mirror.
- Why: versioned, greppable, readable by cloud routines with zero context;
  one place of truth.
- Revisit when: the founder needs mobile browsing of backlog badly enough
  to justify a read-only mirror.

## 2026-09-14: approvals via INBOX.md, digest via Gmail
- Decision: the routine emails a daily digest to the founder only; approval
  state lives in `INBOX.md`.
- Why: works from a phone, no new tooling, the Gmail connector is available
  to cloud routines.
- Revisit when: digests are ignored for two weeks (then weekly) or approvals
  pile up (then a faster channel).

## 2026-09-14: one daily shift, roles as disciplines
- Decision: a single cloud routine per day working one backlog item, roles
  chosen per item; not one routine per role.
- Why: shared context, no PR collisions, no roles inventing work to fill a
  daily report. One-per-role is the evolution once the backlog per role is
  deep.
- Revisit when: the digest routinely reports "nothing to do" (go weekly) or
  the queue never drains (split by role).

## 2026-09-14: first work is discovery, not features
- Decision: the first six backlog items are brief, teardown, discovery plan,
  stack ADR, CI gates, positioning. No product features until BRIEF.md v1.
- Why: building features against an unvalidated thesis is the trap the old
  repo fell into.
- Revisit when: BRIEF.md reaches v1.
```

- [ ] **Step 8: Write `docs/company/BACKLOG.md`**

```markdown
# Backlog

Ordered by priority; the founder reorders. Grammar in TEAM.md.

## FR-1 · pm · BRIEF.md v0 to v0.1: sharpen questions and hypotheses
- state: ready
- gated: no
- why: there is no constitution; every other item needs one to justify itself
- dod:
  - each open question in BRIEF.md has an owner and a concrete way it gets answered
  - the June 2026 brief is read and its claims are listed as hypotheses, not facts
  - failure case: a hypothesis we cannot test within a month is marked "parked", not deleted or silently believed

## FR-2 · pm · Competitive teardown of call-sheet tools
- state: ready
- gated: no
- why: we must know what an AD would have to give up to switch
- dod:
  - docs/research/competitive-teardown.md covers StudioBinder, Yamdu, SetHero, Movie Magic Scheduling, Croogloo
  - for each: how a call sheet is built, revised, distributed, viewed offline; pricing; who the buyer is
  - every claim cites the vendor page or docs it came from, with the date checked
  - failure case: a tool whose behaviour cannot be verified from public sources is marked "unverified", not guessed

## FR-3 · pm · Customer discovery plan: five Prague interviews
- state: ready
- gated: partial
- why: Q1 to Q4 in BRIEF.md can only be answered by the people who make call sheets
- dod:
  - docs/research/discovery-plan.md names the target roles (1st AD, 2nd AD, production coordinator), a 30-minute script, and a note-taking template
  - a draft invitation email exists as text; sending it is an INBOX item, not done by the routine
  - failure case: if fewer than five candidates can be named from the founder's network, the plan says how to find the rest (film schools, FAMU, production listings) instead of shrinking the sample

## FR-4 · tech-lead · ADR-001: stack of the skeleton
- state: ready
- gated: no
- why: the restart from Next.js + Supabase to FastAPI + vanilla PWA must be a recorded decision, not an accident
- dod:
  - docs/adr/ADR-001-stack.md states the options (keep old repo, this skeleton, hybrid), the choice, and the consequences
  - it lists what the old repo had that this one lacks (auth, SSO scaffold, budget, scheduling) and when each would be ported
  - failure case: if a hard requirement in BRIEF.md later contradicts the choice, the ADR names the trigger to revisit rather than being rewritten

## FR-5 · tech-lead · Security and QA gate checklist
- state: ready
- gated: no
- why: gates exist as roles in TEAM.md but not as a checklist anyone can run
- dod:
  - docs/gates/pre-merge-checklist.md with security items (secrets, auth on every non-public route, input validation, dependency pins) and QA items (tests for the change, failure case covered, CI green)
  - the PR template references it
  - failure case: a PR that skips the checklist is visible as such in the template, not silently merged

## FR-6 · marketing · Positioning draft
- state: blocked
- gated: no
- why: outreach and landing need one sentence of positioning that survives contact with an AD
- dod:
  - docs/marketing/positioning.md with alternatives considered and the chosen one, grounded in FR-1 and FR-2 findings
  - blocked until FR-1 and FR-2 are done
  - failure case: if FR-2 shows a competitor already owns the chosen position, the draft says so and proposes another, rather than ignoring it
```

- [ ] **Step 9: Write `STATUS.md`, `INBOX.md`, `LOG.md`**

`docs/company/STATUS.md`:

```markdown
# Status

Updated: 2026-09-14 (founding session)

## pm
- summary: BRIEF.md v0 written as open questions; FR-1 to FR-3 ready.
- tests: n/a
- blockers: none
- needs_approval: no

## engineering (tech-lead + frontend)
- summary: skeleton committed; CI and routine being set up this session.
- tests: 11 pytest (needs Postgres), Playwright smoke pending CI
- blockers: none
- needs_approval: no

## security (gate)
- summary: no gate run yet; checklist is FR-5.
- tests: n/a
- blockers: none
- needs_approval: no

## marketing
- summary: nothing started; FR-6 blocked on FR-1 and FR-2.
- tests: n/a
- blockers: FR-1, FR-2
- needs_approval: no
```

`docs/company/INBOX.md`:

```markdown
# Inbox

Approval queue. Only the founder changes `state`. Grammar in TEAM.md.
Empty at founding.
```

`docs/company/LOG.md`:

```markdown
# Log

One line per unit of work: `YYYY-MM-DD HH:MM · role · text`.

2026-09-14 11:00 · tech-lead · Founding: repo moved, git initialised, company docs created, operating model written.
```

- [ ] **Step 10: Run the checker and all its tests; expect green**

```bash
python scripts/check_company_docs.py docs/company && echo CLEAN
python -m pytest scripts/tests -q
```

Expected: `CLEAN`; 11 passed.

- [ ] **Step 11: Add the README section and commit**

Append to `README.md` after the Stack section:

```markdown
## How this company runs

FilmRunner is run by one founder and an AI team. The operating model,
approval contract, roles and the daily routine are in
`docs/company/TEAM.md`; strategy questions in `docs/company/BRIEF.md`;
work in `docs/company/BACKLOG.md`. Nothing with real-world effect happens
without an approved item in `docs/company/INBOX.md`.
```

```bash
git add docs/company scripts README.md
git commit -m "docs: company brain (TEAM, BRIEF v0, DECISIONS, BACKLOG, STATUS, INBOX, LOG) and format checker

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FBFRX5N8PsXsGvWdB9Y9FU"
git push
```

---

### Task 3: CI with docs check, pytest against Postgres, Playwright smoke

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `frontend/tests/test_smoke.py`, `frontend/tests/requirements.txt`
- Create: `.github/pull_request_template.md`
- Modify: `Makefile` (add `check-docs`, `smoke` targets)

**Interfaces:**
- Produces: a GitHub Actions job named `ci` (the exact context name Task 4's required check uses).
- Consumes: `scripts/check_company_docs.py` from Task 2; `backend/tests` with `FILMRUNNER_DATABASE_URL`.

- [ ] **Step 1: Write the Playwright smoke test (it must fail before the CI wiring exists only in the sense that nothing runs it; locally it can pass)**

`frontend/tests/requirements.txt`:

```
pytest==8.3.3
playwright==1.47.0
pytest-playwright==0.5.2
```

`frontend/tests/test_smoke.py`:

```python
"""Smoke test for the offline-first call sheet PWA.

Serves frontend/ over a local static server and checks the shell renders
and the service worker registers. Data loading against the API is covered
by the backend tests; this guards the app shell that must work with no
signal on set.
"""

import http.server
import socketserver
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page

FRONTEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def frontend_url() -> Iterator[str]:
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *args, directory=str(FRONTEND_DIR), **kwargs
    )
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{port}"
        server.shutdown()


def test_shell_renders(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html")
    assert "call sheet viewer" in page.locator("h1").inner_text()
    assert page.locator("#loadBtn").is_visible()


def test_service_worker_registers(page: Page, frontend_url: str) -> None:
    page.goto(f"{frontend_url}/index.html")
    registered = page.evaluate(
        "navigator.serviceWorker.ready.then(r => Boolean(r.active || r.installing || r.waiting))"
    )
    assert registered is True


def test_load_without_api_shows_offline_status(page: Page, frontend_url: str) -> None:
    """Failure case: no API and no cache must show a visible status, not a blank sheet."""
    page.goto(f"{frontend_url}/index.html")
    page.fill("#apiBase", "http://127.0.0.1:1")
    page.fill("#callSheetId", "00000000-0000-0000-0000-000000000000")
    page.click("#loadBtn")
    page.wait_for_function("document.querySelector('#status').textContent.trim().length > 0", timeout=10_000)
    assert page.locator("#status").inner_text().strip() != ""
```

- [ ] **Step 2: Run the smoke test locally**

```bash
cd ~/Documents/Coding/filmrunner && . backend/.venv/bin/activate
pip install -r frontend/tests/requirements.txt && python -m playwright install chromium
python -m pytest frontend/tests -q
```

Expected: 3 passed. If `test_load_without_api_shows_offline_status` fails because `#status` stays empty, read `frontend/index.html`'s `loadBtn` handler and check what it writes on fetch failure; the assertion must match the real behaviour (the earlier session verified the page shows an offline message when fetch fails and cache is empty), not be loosened.

- [ ] **Step 3: Write the workflow**

`.github/workflows/ci.yml`:

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:

jobs:
  ci:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: filmrunner
          POSTGRES_PASSWORD: filmrunner_dev
          POSTGRES_DB: filmrunner_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    env:
      FILMRUNNER_DATABASE_URL: postgresql+psycopg://filmrunner:filmrunner_dev@localhost:5432/filmrunner_test
      FILMRUNNER_API_BEARER_TOKEN: ci-only-token
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install
        run: |
          pip install -r backend/requirements.txt -r frontend/tests/requirements.txt
          python -m playwright install --with-deps chromium
      - name: Company docs format
        run: python scripts/check_company_docs.py docs/company
      - name: Checker tests
        run: python -m pytest scripts/tests -q
      - name: Backend tests
        working-directory: backend
        run: python -m pytest tests -q
      - name: Frontend smoke
        run: python -m pytest frontend/tests -q
```

- [ ] **Step 4: PR template and Makefile targets**

`.github/pull_request_template.md`:

```markdown
## What and why

<!-- one paragraph; link the BACKLOG item (FR-n) -->

## Gates (see docs/company/TEAM.md; checklist detail lands with FR-5)

- [ ] Tests cover the change, including one failure case
- [ ] No secrets, tokens, or personal data added
- [ ] Every non-public route requires auth
- [ ] `python scripts/check_company_docs.py` is clean
- [ ] Nothing here sends, spends, publishes, or deploys without an approved INBOX item
```

Add to `Makefile`:

```makefile
check-docs:
	python3 scripts/check_company_docs.py docs/company

smoke:
	cd frontend && python3 -m pytest tests -q
```

and extend `.PHONY` with `check-docs smoke`.

- [ ] **Step 5: Commit, push, watch CI**

```bash
git add .github frontend/tests Makefile
git commit -m "ci: docs format check, backend tests on Postgres, PWA Playwright smoke, PR template

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FBFRX5N8PsXsGvWdB9Y9FU"
git push
gh run watch --exit-status
```

Expected: the `ci` job passes. If the backend step fails on DB connection, the Postgres service is not healthy yet; the `options` health check above handles it, so read the log before changing anything.

---

### Task 4: `main` rules: required `ci` check, or documented fallback

**Files:**
- Modify: `docs/company/DECISIONS.md` (append the outcome)
- Modify: `docs/company/TEAM.md` (runbook line on how `main` is protected)

**Interfaces:**
- Consumes: job name `ci` from Task 3.

- [ ] **Step 1: Try a ruleset requiring the `ci` check on `main`**

```bash
cd ~/Documents/Coding/filmrunner
gh api -X POST repos/sandovabarbora/filmrunner/rulesets \
  -f name="main: ci required" -f target=branch -f enforcement=active \
  --input - <<'JSON'
{
  "name": "main: ci required",
  "target": "branch",
  "enforcement": "active",
  "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
  "rules": [
    {"type": "required_status_checks",
     "parameters": {"strict_required_status_checks_policy": false,
                    "required_status_checks": [{"context": "ci"}]}}
  ]
}
JSON
```

Expected on a free personal account with a private repo: HTTP 403 with a message about upgrading. Expected if the account allows it: HTTP 201 with the ruleset JSON.

- [ ] **Step 2: Record the outcome**

If 201: append to `DECISIONS.md`:

```markdown
## 2026-09-14: main protected by a ruleset requiring the ci check
- Decision: pushes to main must have the `ci` status check green (ruleset "main: ci required").
- Why: makes "code only via green PR" enforced, not just agreed.
- Revisit when: the routine's direct commits of STATUS/INBOX/LOG fail the check (they trigger ci on push; if that is too slow, exempt docs-only pushes via paths-ignore in ci.yml and re-check).
```

If 403: append instead:

```markdown
## 2026-09-14: main is protected by contract, not by GitHub rules
- Decision: GitHub rulesets on private repos need a paid plan on this account; "code only via green PR" is enforced by TEAM.md and the PR template, and audited via `git log main --no-merges` in the Monday digest.
- Why: not worth paying for at zero users; the routine is the only other committer.
- Revisit when: a second human committer appears, or the repo goes public.
```

Note for either branch: the routine's direct pushes of the three state files also trigger `ci` on `main`; that is acceptable (docs check runs in seconds; the whole job takes a few minutes and costs nothing on a private repo within the free minutes).

- [ ] **Step 3: Commit**

```bash
git add docs/company/DECISIONS.md docs/company/TEAM.md
git commit -m "docs: record how main is protected

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01FBFRX5N8PsXsGvWdB9Y9FU"
git push
```

---

### Task 5: Create the daily routine and run it once now (also verifies Artifact tool availability)

**Files:**
- Create: `docs/company/routine-prompt.md` (the exact prompt, versioned so changes are reviewable)
- Modify: `docs/company/DECISIONS.md` (Artifact-tool outcome)

**Interfaces:**
- Consumes: TEAM.md contract, BACKLOG grammar, `sandovabarbora/filmrunner` on GitHub, Gmail connector `12b17832-15d9-4929-a1ef-4b7013c446f4`, environment `env_014cSNvbMP2YNUgbAhD5uWXn`.
- Produces: a routine id, recorded in TEAM.md runbook.

- [ ] **Step 1: Write the prompt file**

`docs/company/routine-prompt.md`:

```markdown
You are the FilmRunner daily shift. You start with zero context; everything you need is in this repository.

FIRST: read docs/company/TEAM.md in full and follow its approval contract literally. Then read docs/company/BRIEF.md, BACKLOG.md, INBOX.md, STATUS.md.

Hard rules (a violation is a bug):
- Never push code to main. Code goes on a branch named shift/<backlog id> and a pull request.
- The only files you may commit directly to main are docs/company/STATUS.md, INBOX.md, LOG.md. Run `git pull --rebase origin main` before pushing them; never force-push.
- The only email you may send is one digest to sandovabarb@gmail.com. Never any other recipient, never a CC.
- Never spend money, create accounts, publish, or deploy. If a task needs that, append an INBOX.md item (grammar in TEAM.md) and move on.
- Run `python scripts/check_company_docs.py docs/company` before committing BACKLOG.md or INBOX.md; fix problems it prints.

Work, in order:
1. INBOX.md items with `state: approved` that are doable inside the repo (merging a PR whose ci check is green): do them, set `state: done`. Approved items that need the founder's credentials or money: leave them, note "waiting for founder, manual" in STATUS.md.
2. Pick the highest BACKLOG.md item with `state: ready` and `gated: no` (or `partial`, doing only the ungated part). Work in the role the item names, to a staff-level standard: understand before building, design first, test first, name what you verified and what you did not. Deliver to the item's dod. Set the item to `in-progress`, or `done` when the PR is the entire deliverable. Open the PR with `gh pr create`, body linking the item.
3. Write STATUS.md for every role (summary, tests, blockers, needs_approval), append one LOG.md line, commit these to main.
4. Send the digest via the Gmail tool to sandovabarb@gmail.com, subject "FilmRunner směna <date>", in Czech, max five lines: co se udělalo, co čeká na schválení (#id), co je blokované, odkaz na PR. If today is Monday, add a short proposed plan for the week.
5. Do at most one backlog item. If nothing is workable, send one line: "nic k práci, backlog potřebuje tebe", and stop.

Board sync: if a tool to write to an Artifact database is available to you, after step 3 write one document per role to status/<role> with fields summary, tests_status, blockers, needs_approval (boolean), updated_at (ISO) and one document to log/<uuid> with role, text, at; then add the line "board: synced" to the digest. If no such tool exists, add "board: no artifact tool" to the digest and do nothing else about it.
```

- [ ] **Step 2: Re-check the current time and compute the cron**

```bash
date -u +%Y-%m-%dT%H:%M:%SZ
```

Europe/Prague on 2026-09-14 is UTC+2 (CEST), so 05:00 Prague = 03:00 UTC: cron `0 3 * * *`. Confirm this with the founder before creating. After the DST change on 2026-10-25 it becomes `0 4 * * *` (runbook already says so).

- [ ] **Step 3: Create the routine (show the founder this config first, then create)**

Load the tool: `ToolSearch select:RemoteTrigger`. Then `RemoteTrigger` with `action: "create"` and body (prompt = the full text of `docs/company/routine-prompt.md`, uuid freshly generated with `uuidgen | tr A-Z a-z`):

```json
{
  "name": "FilmRunner daily shift",
  "cron_expression": "0 3 * * *",
  "enabled": true,
  "mcp_connections": [
    {"connector_uuid": "12b17832-15d9-4929-a1ef-4b7013c446f4", "name": "Gmail", "url": "https://gmailmcp.googleapis.com/mcp/v1"}
  ],
  "job_config": {
    "ccr": {
      "environment_id": "env_014cSNvbMP2YNUgbAhD5uWXn",
      "session_context": {
        "model": "claude-sonnet-5",
        "sources": [{"git_repository": {"url": "https://github.com/sandovabarbora/filmrunner"}}],
        "allowed_tools": ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]
      },
      "events": [{"data": {"uuid": "<fresh uuid>", "session_id": "", "type": "user", "parent_tool_use_id": null,
                 "message": {"role": "user", "content": "<contents of docs/company/routine-prompt.md>"}}}]
    }
  }
}
```

Expected: a response with the routine id; link `https://claude.ai/code/routines/<id>`.

- [ ] **Step 4: Run it once now and read the log**

`RemoteTrigger` `{action: "run", trigger_id: "<id>"}`, then after it finishes `{action: "list_runs", trigger_id}` and `{action: "get_run_log", session_id}`.

Verify in the log and in the repo:
- a branch `shift/FR-1` and a PR exist (`gh pr list`);
- `main` received only STATUS/INBOX/LOG commits (`git fetch && git log origin/main --stat -3`);
- one email arrived at `sandovabarb@gmail.com` (Gmail MCP `search_threads` with `subject:"FilmRunner směna"`), no other sends (the log shows every tool call);
- the digest says either `board: synced` or `board: no artifact tool`.

- [ ] **Step 5: Record the outcomes**

Append to `DECISIONS.md` (choose the branch that matches the digest):

```markdown
## 2026-09-14: status board is synced from interactive sessions
- Decision: the cloud routine has no Artifact tool (verified in the first run log: "<quote the digest line>"), so the "AI Team Status" board is synced manually at the end of interactive sessions from STATUS.md and LOG.md.
- Why: verified, not assumed; the email digest is the always-current channel anyway.
- Revisit when: routines gain an Artifact or HTTP capability.
```

or, if synced:

```markdown
## 2026-09-14: status board is synced by the routine
- Decision: the routine writes status/<role> and log/<id> to the board's artifact DB at the end of every run (verified in the first run).
- Why: the board is then as current as the digest.
- Revisit when: a run leaves the board half-written (then move sync to the last step and make it idempotent).
```

Add the routine id and URL to the runbook section of `TEAM.md`. Commit and push both files.

---

### Task 6: First board sync from this session

**Files:**
- None in the repo; writes to the artifact DB of `https://claude.ai/code/artifact/51819ede-1d6e-4974-b322-67347fb0532a`.

**Interfaces:**
- Consumes: `docs/company/STATUS.md` and `LOG.md` as of the end of Task 5. Board schema from the artifact source: `status/{role}` documents with `summary`, `tests_status`, `blockers`, `needs_approval`, `updated_at`; `log/{id}` documents with `role`, `text`, `at`. Role ids on the board: `product`, `engineering`, `security`, `marketing` (map `pm` → `product`, `tech-lead`/`frontend` → `engineering`).

- [ ] **Step 1: Skip if Task 5 verified the routine already synced the board (read `status/engineering` with `read_db` `get`; if `updated_at` is today, stop here).**

- [ ] **Step 2: Write the four status documents and one log line in one batch**

`Artifact` `action: "write_db"`, `db_op: "batch"`, `url` = the board URL, `writes` =

```json
[
 {"op":"set","collection":"status","doc_id":"product","data":{"summary":"<pm summary from STATUS.md>","tests_status":"n/a","blockers":"","needs_approval":false,"updated_at":"<now ISO>"}},
 {"op":"set","collection":"status","doc_id":"engineering","data":{"summary":"<engineering summary>","tests_status":"<from STATUS.md>","blockers":"","needs_approval":false,"updated_at":"<now ISO>"}},
 {"op":"set","collection":"status","doc_id":"security","data":{"summary":"<security summary>","tests_status":"n/a","blockers":"","needs_approval":false,"updated_at":"<now ISO>"}},
 {"op":"set","collection":"status","doc_id":"marketing","data":{"summary":"<marketing summary>","tests_status":"n/a","blockers":"FR-1, FR-2","needs_approval":false,"updated_at":"<now ISO>"}},
 {"op":"set","collection":"log","doc_id":"<uuid>","data":{"role":"engineering","text":"Founding: repo, company docs, CI, daily routine created.","at":"<now ISO>"}}
]
```

`needs_approval` is `true` for a role only if `INBOX.md` has a `pending` item for it.

- [ ] **Step 3: Verify**

`Artifact` `action: "read_db"`, `db_op: "list"`, `collection: "status"`: four documents with today's `updated_at`. Open the board URL and confirm the four cards show text, not "No run yet."

---

### Task 7: Memory

**Files:**
- Modify: `/Users/barbora.sandova/Documents/memory/decisions.md` (append)
- Modify: `/Users/barbora.sandova/Documents/memory/preferences.md` (append one line)

- [ ] **Step 1: Append to `decisions.md`**

```markdown
## 2026-09-14 — FilmRunner: založení firmy s AI týmem, restart na skeleton
- **Decision:** Kanonický kód = `~/Documents/Coding/filmrunner` (FastAPI + vanilla PWA skeleton, GitHub `sandovabarbora/filmrunner`, private). `~/Documents/Coding/sandbox/film_production` je reference, ne produkt. Strategie od nuly: červnový PRODUCT_BRIEF je vstup. Firemní mozek = `docs/company/` (TEAM, BRIEF, DECISIONS, BACKLOG, STATUS, INBOX, LOG). Jedna denní cloud routine 05:00 Praha (Sonnet, jen Gmail konektor, max. jedna položka/běh, digest jen na sandovabarb@gmail.com). Board artifact = projekce STATUS/LOG. Bára hands-on 10+ h/týden.
- **Why:** Vědomý restart kolem call sheetu; jedna směna místo čtyř agentů kvůli sdílenému kontextu a šumu; repo jako pravda, aby cloud agent bez kontextu fungoval.
- **Approval kontrakt:** autonomně research/kód na branch/PR/drafty; nikdy merge do main, e-mail cizím, peníze, publikace, účty, infra bez `approved` položky v INBOX.md.
- **Spec:** `docs/superpowers/specs/2026-09-14-ai-team-operating-model-design.md` v repu.
- **Revisit when:** digest je dva týdny „nic k práci" (→ týdně) nebo fronta neschne (→ routine na roli).
```

- [ ] **Step 2: Append to `preferences.md`**

```markdown
- **FilmRunner: vždy nejdřív `docs/company/TEAM.md` a `BACKLOG.md`, pak role.** Při každém FilmRunner úkolu přečíst company docs, říct, kterou roli (pm / tech-lead / frontend / marketing / gate) jsem zvolila, a nic s dopadem ven bez `approved` položky v INBOX.md. Zavedeno 2026-09-14 při založení.
```

- [ ] **Step 3: Verify the memory files still parse as before**

```bash
tail -12 /Users/barbora.sandova/Documents/memory/decisions.md
tail -3 /Users/barbora.sandova/Documents/memory/preferences.md
```

Expected: the new entries appear, nothing else changed (`git diff` not available there; eyeball the tails).

---

## Self-review against the spec

- §2 repo + brain → Tasks 1, 2. §2 approval contract → TEAM.md (Task 2) and the routine prompt (Task 5).
- §3 roles → TEAM.md roles table. §4 routine → Task 5 (prompt mirrors the seven-step contract; state files direct to main; Gmail-only). §4 `main` rules → Task 4 with both outcomes.
- §5 board → Task 5 verification + Task 6 fallback. §6 first backlog → BACKLOG.md. §7 order → task order. §8 risks: secrets (Task 1 step 2 check), third-party email (prompt hard rule + Task 5 step 4 verification), concurrent edits (prompt: rebase, never force), cost (one item, Sonnet). §9 unverified items each have a verifying step (Task 4 step 1, Task 5 step 4, Task 5 step 2).
- Names used consistently: job `ci`; role ids `pm, tech-lead, frontend, marketing, security, qa`; board ids `product, engineering, security, marketing`; checker functions `check_backlog`, `check_inbox`, `main`, `ROLES`.
