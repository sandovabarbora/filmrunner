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

**Hackathon mode, 2026-09-21 to 2026-09-25 (founder's call):** every PR
with a green `ci` check auto-merges, code and ADRs included. Only
`docs/company/TEAM.md` still waits for the founder. Accounts, money,
secrets, deploys and email to anyone but the founder stay gated as
below. A PR that changes `backend/` must say "backend changed: deploy
needed" in its body and in the digest; the founder (or her session) runs
`cd backend && fly deploy`. After 2026-09-25 the reversibility rule below
applies again unless the founder extends the mode.

`main` accepts only commits whose `ci` check is green (GitHub ruleset;
direct pushes are rejected). Outside hackathon mode, what may auto-merge
is decided by reversibility, not by who wrote it:

- **Auto-merge (reversible, the founder can edit or revert any time):**
  state files (`docs/company/STATUS.md`, `INBOX.md`, `LOG.md`), backlog
  proposals (`docs/company/BACKLOG.md` additions and `state:` changes),
  research and marketing documents (`docs/research/**`, `docs/marketing/**`),
  gate checklists (`docs/gates/**`), and `.github/pull_request_template.md`.
  A PR that touches only these paths gets `gh pr merge --auto --squash`.
- **Founder merges (decisions and code):** anything under `backend/`,
  `frontend/`, `scripts/`, `.github/workflows/`, and the decision documents
  `docs/adr/**`, `docs/company/BRIEF.md`, `TEAM.md`, `DECISIONS.md`.

Rule added 2026-09-17 after two idle days: every proposal and every docs
deliverable had waited on a founder merge, so no item was ever `ready`.

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

## Product rule: connect first, then add

Every item starts by naming how it plugs into the flow that already exists
(entry page → editor → production → day → crew link → viewer), and the PR
shows that path working end to end. A feature that works on its own but
is reachable only by URL or curl is not done. Founder, 2026-09-14, after
the first day produced working pieces that did not yet form one app.

## Conventions (checked in CI)

- Branch: `<type>/<what-it-does>` where type is one of `feat`, `fix`,
  `docs`, `chore`, `refactor`, `test`, `ci`; lowercase, hyphens.
  Examples: `docs/fr-2-competitive-teardown`, `chore/shift-state-2026-09-14`,
  `feat/call-sheet-pdf-export`.
- Commit and PR title: Conventional Commits, `type(scope): subject`, scope
  optional, subject in the imperative, no trailing period.
  Examples: `docs(pm): FR-2 competitive teardown`, `fix(api): reject 27th revision`.
- `main` history is squash-only; the squash title is the commit title.
- CI rejects a PR whose branch or title breaks these rules.

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

## Working hours (cloud routines)

The team works Monday to Friday, 08:00 to 18:00 Europe/Prague, as two
cloud routines (model claude-sonnet-5, clone of this repo, Gmail connector
only; tools Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch; the
cloud also provides a GitHub MCP for PRs; WebFetch is egress-blocked for
most external domains, WebSearch works):

- **Morning brief, 08:00**: plans the day into a `## today` section of
  `STATUS.md` (one backlog item per shift), refills the backlog with a
  proposals PR when fewer than three ready items remain, and emails the
  founder the plan plus what awaits her. Prompt: `routine-brief-prompt.md`.
- **Shifts hourly 09 to 17 during hackathon mode (09, 11, 13, 15, 17 otherwise)**: each works one item per the contract
  below. Shifts 09 to 15 email only when they produced a PR or an INBOX
  item; the 17 shift always emails the day summary. Prompt:
  `routine-shift-prompt.md`.

Shift contract:

1. Read `TEAM.md`, `BRIEF.md`, `BACKLOG.md`, `INBOX.md`, `STATUS.md`.
2. Execute `approved` inbox items that are doable inside the repo
   (typically merging a PR) and mark them `done`. Approved items that need
   credentials or money: do not execute; write "waiting for founder,
   manual" in `STATUS.md`.
3. Take the highest `ready` backlog item with `gated: no`. Work in the role
   the item names, to its DoD. Code only on branch `<type>/<id>-<slug>`
   (e.g. `docs/fr-2-competitive-teardown`); tests must pass; open a PR. Discovery and marketing outputs are markdown under
   `docs/` on the same branch. Set the item to `in-progress` (or `done`
   when the PR is the whole deliverable and only awaits merge).
4. When something needs approval, append an `INBOX.md` item and continue
   with the next ungated item. Never block.
5. Write `STATUS.md` (per role: summary, tests, blockers, needs_approval)
   and one `LOG.md` line. Commit these files on
   `chore/shift-state-<date>-<HHMM>`, open a PR, enable auto-merge
   (`gh pr merge --auto --squash`).
6. Digest to `sandovabarb@gmail.com` only, in Czech: shifts 09 to 15 only
   when they produced something (five lines: what, what awaits approval,
   what is blocked, PR link); the 17 shift always sends the day summary.
6b. An `in-progress` item whose note names remaining ungated work is
   plannable; finishing a half-done item beats starting a new one.
7. At most one backlog item per run. Never start an item whose dod depends
   on a pull request that is still open. A shift with nothing workable acts
   as the pm for that run: it proposes one new backlog item (serving an
   open BRIEF question, with dod and failure case, `state: ready`) in an
   auto-merged proposals PR, so the next shift has work; then it writes
   its state PR and stays silent.

### Runbook

- Routine list and logs: from an interactive Claude Code session, load
  `RemoteTrigger` and call `list_runs` then `get_run_log` for the run in
  question. A run that was skipped before a session existed leaves no run;
  check the routine itself with `get`.
- Cron is in UTC. In winter time (after the last Sunday of October) every
  hour above shifts by one: `0 7 * * 1-5` for the brief, `0 8,10,12,14,16 * * 1-5`
  for the shifts. Update both routines at DST changes or accept a one-hour drift.
- Shifts routine: `trig_012VzQ17vcMx1FwKu4ZSYYBC`, cron `0 7,9,11,13,15 * * 1-5` UTC
  (09, 11, 13, 15, 17 Prague in summer time). Morning brief routine:
  `trig_01Qoi6RkCkgTc5pdH7jm3Wtb`, cron `0 6 * * 1-5` UTC (08:00 Prague in summer time).
  Edit/disable: https://claude.ai/code/routines
- If the routine sent email to anyone other than the founder, or
  auto-merged a PR containing code: disable it at the URL above, record the incident in
  `DECISIONS.md`, fix the prompt, re-enable.

## Status board

The "AI Team Status" artifact (four cards: product, engineering, security,
marketing; activity log) is a projection of `STATUS.md` and `LOG.md`. It is
synced by interactive sessions (step "sync board": read `STATUS.md` and
`LOG.md`, write `status/<role>` and `log/<id>` via the Artifact tool).
The routine does not sync it: verified 2026-09-14 in two runs that the
Artifact write raises a permission prompt no one can answer in the cloud,
which stalls the run. The email digest is always the current channel.
