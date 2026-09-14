# FilmRunner: AI team operating model (design)

Date: 2026-09-14. Status: approved in conversation, pending written review.
Author: Claude (Tech Lead / EM role), decisions by Barbora Sandova.

## 0. Decisions this design rests on

Made 2026-09-14 in conversation, each one a fork that changes everything below:

| Decision | Choice | Rejected alternative |
|---|---|---|
| Canonical code | Today's skeleton (`filmrunner`, FastAPI + vanilla PWA) | `~/Documents/Coding/sandbox/film_production` (Next.js + FastAPI + Supabase). Becomes reference material only. |
| Strategy | Founded from scratch. June 2026 `PRODUCT_BRIEF.md` is an input, not a conclusion. | Keep the June brief as constitution. |
| Founder's role | Hands-on, 10+ h/week, in everything. | Board-only / tech-lead-only. |
| Company brain | Markdown in the repo, versioned with git. | Notion, or repo + Notion mirror. |
| Approval channel | Gmail digest + `INBOX.md` in repo. | Repo only; Slack/Notion. |
| Team topology | One daily "shift" routine, roles as disciplines. | One routine per role (later evolution); no routines. |

## 1. Goal

Run FilmRunner as a company staffed by one human founder plus an AI team
that does product, engineering, marketing and security work to a
staff-level standard, works when the founder is absent, and never takes an
action with real-world effect without explicit approval.

Success in the first month: a `BRIEF.md` v1 the founder signed off, a
competitive teardown, a discovery plan with interviews scheduled, one ADR on
the stack, CI with a security/QA gate, and a daily digest that has arrived
every morning without noise.

Out of scope for this design: new product features, landing page, pricing
page, any deployment. Those wait for `BRIEF.md` v1.

## 2. Repository and company brain

Move `~/Downloads/filmrunner` to `~/Documents/Coding/filmrunner`. `git init`,
first commit is the current skeleton. Remote: private GitHub repo
`sandovabarbora/filmrunner`. `film_production` stays untouched; a
`DECISIONS.md` entry records it as reference, not product.

`docs/company/` is the single source of truth. Every interactive session and
every routine reads it before doing anything.

| File | Content | Writer |
|---|---|---|
| `BRIEF.md` | Constitution: thesis, customer, business model, out-of-scope, kill criteria. Starts as a list of open questions and hypotheses. | PM role drafts, founder approves |
| `DECISIONS.md` | Dated ADR-style entries: decision, why, revisit-when. Append-only. | Any role; founder confirms |
| `BACKLOG.md` | Prioritised items: `id`, role, why, definition of done (with a failure case), `gated: yes/no/partial`, state (`ready`, `in-progress`, `blocked`, `done`) | PM proposes, founder orders |
| `STATUS.md` | Latest state per role: summary, tests status, blockers, `needs_approval`. Overwritten. | Every session and routine |
| `INBOX.md` | Approval queue: `#id`, what, why, risk, proposal, state (`pending`, `approved`, `rejected`, `done`) | Roles and routine append; only the founder changes state |
| `LOG.md` | One line per unit of work: timestamp, role, text. Append-only. | Every session and routine |
| `TEAM.md` | Roster, operating model, approval contract, routine runbook. Prose, readable by a cloud agent with zero context. | Written at founding, founder approves |

### Approval contract (verbatim into `TEAM.md`)

The team may, without asking: read anything; write to the repo on a branch;
open pull requests; write drafts (emails, copy, PRDs, ADRs); do web
research; update `STATUS.md`, `INBOX.md`, `BACKLOG.md`, `LOG.md`.

The team may not, unless an `INBOX.md` item is `approved`: merge to `main`;
send email to anyone other than the founder; spend money; publish anything
publicly; create accounts on services; change DNS or infrastructure.

Violating this is a bug, not initiative. Approved items that need the
founder's own credentials (accounts, payments, sending from her address to
third parties) are executed by the founder in an interactive session, never
by the routine.

## 3. Roles

Roles are disciplines the assistant switches into, not separate agents.
Each combines a `dev-team` role file with already-installed skills. When a
task arrives, the assistant names the role it chose (dev-team rule).

| Role | Discipline source | Accountable for now |
|---|---|---|
| PM | `dev-team/pm.md` + `idea-validation`, `customer-research`, `competitive-teardown`, `pricing` | `BRIEF.md` from scratch; backlog ordering proposals |
| Tech Lead / Backend | `tech-lead.md`, `backend-python.md`, `dba.md` | Skeleton architecture, ADRs, review standard, API contract |
| Frontend | `frontend.md` + `impeccable` | PWA, offline behaviour, crew-facing call sheet on mobile |
| Marketing / GTM | `product-marketing`, `launch`, `content-strategy`, `cold-email` | Positioning, Prague go-to-market, outreach drafts (gated) |
| Security (gate) | `security.md` + `security-checklist` | Checklist run before every merge; findings into `STATUS.md` |
| QA (gate) | `qa.md`, `sdet.md` | Tests-first; every DoD has a failure case; pytest + Playwright in CI |

Gates are not daily reporters. The board's Security card shows the last
gate result, not daily activity. Engineering card = Tech Lead + Frontend.

## 4. The daily shift (cloud routine)

Runs in Anthropic cloud from the GitHub repo (verified: routines have no
access to the local machine; minimum interval 1 h; Gmail connector is
available to routines).

- Schedule: daily 05:00 Europe/Prague. Cron is in UTC, so the expression is
  computed at creation time and re-checked at DST changes (documented in the
  runbook). Monday runs additionally propose the week's plan in `STATUS.md`.
- Model: `claude-sonnet-5`. Repo: `sandovabarbora/filmrunner`. Connectors:
  Gmail only. Tools: Bash, Read, Write, Edit, Glob, Grep.
- `main` rules: code changes only via PR with the CI check green (enforced by
  a required status check on GitHub). The three state files
  (`docs/company/STATUS.md`, `INBOX.md`, `LOG.md`) are committed directly
  to `main` by the routine so they are always current. GitHub branch
  protection cannot exempt paths, so "no code directly to main" is a
  contract in `TEAM.md` plus the required check, not a hard lock; a
  violation is visible in `git log` and treated as a bug.

Run contract (the prompt is self-contained and repeats this):

1. Read `TEAM.md`, `BRIEF.md`, `BACKLOG.md`, `INBOX.md`, `STATUS.md`.
2. Execute `approved` inbox items that are doable inside the repo (typically
   merging a PR); mark them `done`. Approved items needing credentials or
   money: do not execute, note "waiting for founder, manual" in `STATUS.md`.
3. Take the highest `ready` backlog item with `gated: no`. Work in the role
   the item names, to its DoD. Code only on branch `shift/<id>`, tests must
   pass, open a PR. Discovery and marketing outputs are markdown under
   `docs/` on the same branch.
4. When something needs approval, append an `INBOX.md` item and continue
   with the next ungated item. Never block.
5. Write `STATUS.md` (per role: summary, tests, blockers, `needs_approval`)
   and one `LOG.md` line; commit these, and any new `INBOX.md` items,
   directly to `main` (rebase on non-fast-forward, never force).
6. Send a digest to `sandovabarb@gmail.com` and to no other address: five
   lines max, what was done, what awaits approval (`#id`), what is blocked,
   PR link.
7. Budget: at most one backlog item per run. If nothing is workable, send a
   one-line digest ("nothing to do, backlog needs you") and stop. Noise is
   worse than silence.

Failure handling: a run that errors or is skipped is diagnosed with
`RemoteTrigger list_runs` / `get_run_log` from an interactive session; the
runbook in `TEAM.md` describes this. A run must never leave `STATUS.md`
half-written: write status last, in one step.

## 5. Shop window: board and digest

`STATUS.md` and `LOG.md` are truth. The existing "AI Team Status" artifact
(four cards, activity log, `status/{role}` and `log/{id}` documents) is a
projection.

Open question to verify during implementation, not assume: whether a cloud
routine has the Artifact tool with `write_db`. If yes, the routine syncs the
board at the end of each run. If no (expected), an interactive session step
"sync board" reads `STATUS.md` + `LOG.md` and writes the documents; the board
then shows "state as of last session", and the email digest remains the
always-current channel. The outcome is recorded in `DECISIONS.md`.

Board structure stays as is: four cards, `needs approval` chip driven by
`INBOX.md` pending items for that role.

## 6. First backlog (founder reorders)

| # | Role | Item | gated |
|---|---|---|---|
| 1 | PM | `BRIEF.md` v0: open questions + hypotheses; June brief and `film_production` are inputs | no |
| 2 | PM | Competitive teardown: StudioBinder, Yamdu, SetHero, Movie Magic, Croogloo; what they do with the call sheet and what they do not | no |
| 3 | PM | Customer discovery plan: 5 interviews with 1st ADs / production managers in Prague, interview script. Sending invitations is gated. | partial |
| 4 | Tech Lead | ADR-001: skeleton stack (FastAPI + vanilla PWA) vs. Next.js, with explicit "why not the large repo" | no |
| 5 | Tech Lead | Security/QA gate checklist as a file + CI (GitHub Actions: pytest, Playwright smoke) | no |
| 6 | Marketing | Positioning draft; blocked until #1 and #2 are done | no, blocked |

Deliberately absent: product features, landing, pricing page, deployment.

## 7. Implementation order

1. Move repo, `git init`, first commit, private GitHub remote.
2. `docs/company/*` files with the content above; `TEAM.md` with the
   contract and runbook.
3. CI (pytest + Playwright smoke) and branch protection.
4. Verify Artifact tool availability in routines; record outcome.
5. Create the routine via `/schedule`, config shown to the founder before
   creation, cron converted from 05:00 Prague and confirmed.
6. First manual "sync board" from an interactive session.
7. Memory: `decisions.md` entries for the six decisions in section 0.

## 8. Risks and how they are contained

- Routine emails a third party: prompt and `TEAM.md` restrict to one
  address; digest is the only send; any other send is a bug to report.
- Secrets in repo: `.env` ignored from the first commit; `.env.example` only;
  dev bearer token is documented as dev-only.
- Routine and founder edit the same state file concurrently: the routine
  rebases before pushing and never force-pushes; if the rebase conflicts it
  keeps the founder's version, reports the conflict in the digest, and puts
  its own update in the PR description instead.
- Cost creep: one item per run, Sonnet, daily. Revisit if the digest is
  routinely "nothing to do" (reduce to weekly) or always has a queue
  (consider approach B, one routine per role).
- Design drifts from `BRIEF.md`: every backlog item cites the brief section
  it serves; items that cannot are `blocked` until the brief has an answer.

## 9. Verified vs. not yet verified

Verified in this session: the large `film_production` repo exists with the
June brief and 40 uncommitted files; the skeleton has passing tests and a
verified offline PWA; cloud routines run from GitHub with no local access,
1 h minimum interval, Gmail connector available to them; the board artifact
reads `status/{role}` and `log/{id}` from an artifact DB.

Not yet verified: Artifact tool availability inside a routine; whether the
required-status-check rule can be set with `gh` on this account (else via
the GitHub UI); exact UTC cron for 05:00 Prague at creation time.
