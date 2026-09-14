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

Reference material, never a source of truth: the June 2026 brief, copied
to `docs/reference/PRODUCT_BRIEF-2026-06.md`, and the old codebase in
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

`main` accepts only commits whose `ci` check is green (GitHub ruleset;
direct pushes are rejected). Code reaches `main` through a pull request the
founder merges. The routine's state updates (`docs/company/STATUS.md`,
`INBOX.md`, `LOG.md`) go through a state-only PR on `shift/state-<date>`
with auto-merge enabled, so they land as soon as `ci` passes. The routine
never enables auto-merge on a PR that touches anything else.

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
   and one `LOG.md` line. Commit these files on `shift/state-<date>`, open
   a PR, enable auto-merge (`gh pr merge --auto --squash`).
6. Send the digest to `sandovabarb@gmail.com` only, in Czech, five lines
   max: what was done, what awaits approval (#id), what is blocked, PR link.
   On Mondays add a proposed plan for the week.
7. At most one backlog item per run. If nothing is workable, send a one-line
   digest ("nic k práci, backlog potřebuje tebe") and stop.

The exact prompt the routine runs is versioned in `routine-prompt.md`.

### Runbook

- Routine list and logs: from an interactive Claude Code session, load
  `RemoteTrigger` and call `list_runs` then `get_run_log` for the run in
  question. A run that was skipped before a session existed leaves no run;
  check the routine itself with `get`.
- Cron is in UTC. 05:00 Prague is 03:00 UTC in summer time and 04:00 UTC in
  winter time; update the cron expression at DST changes (late March, late
  October) or accept a one-hour drift.
- Routine: `trig_012VzQ17vcMx1FwKu4ZSYYBC`, created 2026-09-14, cron `0 3 * * *` UTC.
  Edit/disable: https://claude.ai/code/routines/trig_012VzQ17vcMx1FwKu4ZSYYBC
- If the routine sent email to anyone other than the founder, or
  auto-merged a PR containing code: disable it at the URL above, record the incident in
  `DECISIONS.md`, fix the prompt, re-enable.

## Status board

The "AI Team Status" artifact (four cards: product, engineering, security,
marketing; activity log) is a projection of `STATUS.md` and `LOG.md`. It is
synced from an interactive session with the step "sync board" unless the
routine is verified to have the Artifact tool (see `DECISIONS.md`). The
email digest is always the current channel; the board may lag.
