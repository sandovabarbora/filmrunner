# The branch/PR-title conventions CI gate confirmed to fire end to end (FR-170), 2026-10-14

`TEAM.md` states flatly "CI rejects other branch names and titles" and `DECISIONS.md`'s
2026-09-14 entry records the branch ruleset rejecting a *direct push* to `main`, but — the
same gap FR-127/FR-157/FR-162/FR-164/FR-166 each found in a different subsystem — the
branch-name/PR-title check itself (`.github/workflows/ci.yml`'s "Branch and PR title
conventions" step, `scripts/check_conventions.py`) had only ever been exercised by
`scripts/tests/test_check_conventions.py`'s local pytest calls against the pure
`check_branch`/`check_title` functions. Nobody had opened a real pull request with a
deliberately non-compliant branch name or title and watched the hosted `ci` job actually
turn red.

## What was run

A throwaway PR, branch `test/fr-170-ci-title-gate-throwaway` (itself conventionally named,
so only the *title* check was exercised, per this item's own dod), title deliberately set to
`this is not a conventional commit title` — PR #498.

## Result: the gate fires end to end, confirmed directly

- The hosted `ci` job's "Branch and PR title conventions" step ran
  `python scripts/check_conventions.py "test/fr-170-ci-title-gate-throwaway" "this is not a
  conventional commit title"` with `BRANCH`/`TITLE` populated exactly as `ci.yml` wires them
  (`github.head_ref` / `github.event.pull_request.title`) — confirmed from the job's own env
  block in the log, not assumed.
- The step printed `title 'this is not a conventional commit title' must look like
  'type(scope): subject' with type in ('feat', 'fix', 'docs', 'chore', 'refactor', 'test',
  'ci'), no trailing period` and exited 1, which GitHub Actions reports as `Process completed
  with exit code 1` — the `ci` check run's `conclusion` is `failure`.
  Run: https://github.com/sandovabarbora/filmrunner/actions/runs/38555002693/job/115821901016
- Reading the PR directly (not assumed from the check alone): `pull_request_read get` on PR
  #498 while that check was red returned `"mergeable_state": "blocked"` — the repository's
  branch ruleset does withhold a clean/mergeable status while this check is failing, the
  second half of this item's dod.
- PR #498 was closed without merging once both of the above were recorded, per the item's own
  dod (no further clutter left open, the FR-150/#414 precedent this routine has flagged
  before).

## Conclusion

No wiring gap found — unlike FR-162's axe-core finding, this gate behaves exactly as
`TEAM.md`/`DECISIONS.md` describe it: a real non-compliant PR title turns the hosted `ci`
check red and the branch ruleset blocks merge while it stays red. No `tech-lead` follow-up
item is needed for this gate.

# The "One Alembic head" migration-conflict CI gate confirmed to fire end to end (FR-171), 2026-10-14

Same family, applied to the last unconfirmed gate in `ci.yml`: `scripts/check_migrations.sh`
("One Alembic head", line 87-88) has run on every PR since it was added, but no shift had
ever created a real two-head migration conflict and watched it turn red — only plausible on
inspection, the same starting point FR-162/164/166/170 each had before testing found (or, for
FR-170, confirmed did not have) a real gap.

## What was run

A throwaway PR, branch `test/fr-171-migration-two-heads-throwaway`, PR #503. Two new,
no-op Alembic migrations (`aa11bb22cc33`, `dd44ee55ff66`) were added to
`backend/alembic/versions/`, both setting `down_revision = "d8f4b1c9a2e6"` — a real existing
revision in the chain, so the two new files share one parent, a genuine two-head conflict
(upgrade/downgrade bodies are both `pass`; the conflict is structural, not a schema change).

Note on the parent revision picked: a naive local script (regex over `revision = "..."` /
`down_revision = "..."`, double-quoted, no type annotation) computed the then-current head as
`d8f4b1c9a2e6` and missed `7feea1cfc0e6` (`backend/alembic/versions/7feea1cfc0e6_push_subscription_403_counter.py`,
2026-10-06, FR-137) entirely — that file uses `revision: str = '...'`/single quotes, a format
the regex didn't match. `7feea1cfc0e6` is main's actual real head. This is a bug in this
item's own disposable verification script, not in `check_migrations.sh` or in main's
migration chain: main has exactly one real head today, confirmed by the hosted job itself
(see below). It meant the two new migrations branch off an older ancestor than main's tip
rather than off the tip directly — still a genuine shared-parent two-head conflict (the two
new files share a parent with each other), the exact shape the dod asks for, just with one
extra pre-existing head counted alongside it in the output. Noted here so a future shift
doesn't mistake the "found 3" result below for a real two-head state on `main` before this
PR.

## Result: the gate fires end to end, confirmed directly

- The hosted `ci` job's "One Alembic head" step ran `sh scripts/check_migrations.sh`,
  which runs the real `python -m alembic heads` (not a mock) against the branch's actual
  migration files. It printed `expected exactly one Alembic head, found 3; run: alembic
  merge -m 'merge' <rev1> <rev2>`, followed by `alembic heads`' own listing:
  `7feea1cfc0e6 (head)`, `aa11bb22cc33 (head)`, `dd44ee55ff66 (head)` — and exited 1.
  GitHub Actions reports this as `Process completed with exit code 1`; the `ci` check run's
  `conclusion` is `failure`. Run:
  https://github.com/sandovabarbora/filmrunner/actions/runs/38570104078/job/115872835721
  (Every later step in the job — `Checker tests`, `Backend tests`, `Frontend smoke`, the
  Lighthouse/PDF and PWA gates — correctly shows `skipped`, confirming the job stops rather
  than continuing past a red migration-head check.)
- Reading the PR directly (not assumed from the check alone), the same cross-check FR-170
  used: `pull_request_read get` on PR #503 while that check was red returned
  `"mergeable_state": "blocked"` — the branch ruleset does withhold merge while this check is
  failing, the second half of this item's dod.
- PR #503 was closed without merging once both were recorded (comment with the run link and
  result, per the FR-170 precedent, then closed). The remote throwaway branch could not be
  deleted this shift (`git push origin --delete` 403'd from this session's proxy, the same
  failure FR-170 hit) — harmless, the PR stays closed; a future shift or the founder can
  delete it.

## Conclusion

No wiring gap found — the last unconfirmed major gate in `ci.yml` behaves exactly as
`TEAM.md`/`DECISIONS.md`/the script's own comment describe it: a real two-head migration
conflict turns the hosted `ci` check red via the actual `alembic heads` command, and the
branch ruleset blocks merge while it stays red. No `tech-lead` follow-up item is needed for
this gate. Combined with FR-162 (axe-core), FR-164/FR-166 (`check_live_stack.py`), and FR-170
(`check_conventions.py`), every gate `ci.yml` runs on every PR has now been exercised end to
end at least once with a real, deliberately non-compliant PR rather than assumed from reading
the script.
