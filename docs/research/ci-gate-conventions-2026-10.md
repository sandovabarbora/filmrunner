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
