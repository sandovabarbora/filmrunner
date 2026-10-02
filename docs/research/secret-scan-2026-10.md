# Full git-history secret scan, 2026-10-02

FR-125. Scope: every commit ever made in this repo, not just `HEAD` of
`main` — the gap FR-91/100/110/117/124's dependency scans never close,
since `pip-audit`/`npm audit` only ever see the current tree.

## Method

- This sandbox's checkout started as a shallow clone (`git log` showed
  only 50/100 commits reachable). `git fetch --unshallow origin` pulled
  the complete history before scanning — a shallow-clone scan would have
  silently missed everything before 2026-09-29 and reported "clean" on a
  history it never actually read. Confirmed with
  `git rev-parse --is-shallow-repository` → `false` after the fetch.
- Installed `gitleaks` 8.16.0 (`apt-get install gitleaks`, Ubuntu
  noble-updates universe — PyPI's own `gitleaks` package is an unrelated
  `ycjcl868/gitleaks` npm/PyPI name-squat, not the real tool, so it was
  not used).
- `gitleaks detect --source . --log-opts="--all" -v --report-format json
  --report-path gitleaks-report.json`. `--log-opts="--all"` scans every
  ref gitleaks' underlying `git log` can see, not just `main` — this
  fetch also pulled every still-open feature/throwaway branch from
  `origin` (e.g. `qa/fr-108-throwaway-fetch`,
  `pm/fr-115-famu-office-docs-throwaway`), so the scan covers commits
  that were squashed out of `main`'s history entirely, not only what
  `main`'s own squash-merge log shows.
- Commit range covered: 354 commits total (confirmed by gitleaks' own
  "354 commits scanned" log line), from the founding commit `81e9fc4`
  (2026-09-14) through `main`'s current HEAD `e1c5644` (2026-10-02),
  plus the extra commits living only on still-open branches.

## Result: clean — no real secret found

32 raw findings, all reviewed individually against their actual diff
content (not accepted on the tool's say-so). All 32 are false positives,
two distinct causes:

| Rule | File | Count | Why it's not a secret |
|---|---|---|---|
| `aws-access-token` | `docs/research/lighthouse-pilot-scale.json` | 22 | Base64-encoded JPEG screenshot data embedded in a Lighthouse report (FR-92/97's own pilot-scale artifact). The regex's `AIDA`/`AKIA`-shaped substring match lands inside the base64 photo bytes (`data:image/jpeg;base64,...`), not any credential. Verified by reading the matched line directly (`git show <commit>:docs/research/lighthouse-pilot-scale.json`): it's inside a `"data": "data:image/jpeg;base64,..."` field. |
| `aws-access-token` | `docs/research/lighthouse-landing.json` | 8 | Same cause, same file type (FR-92's landing-page Lighthouse report), same `data:image/jpeg;base64,...` screenshot field. |
| `generic-api-key` | `frontend/tests/test_push_e2e.py` | 2 | `TEST_VAPID_PUBLIC`/`TEST_VAPID_PRIVATE`, introduced in commit `df838f7e` (FR-16's push E2E test). The file's own comment, two lines above, says why: "A fixed test VAPID public key (not a secret — the private half never leaves the API process's env). Any well-formed 65-byte uncompressed-point base64url string works, since `PushManager.subscribe` itself is stubbed in this test." These are throwaway fixture values the test generated for itself; the real production VAPID keypair (INBOX #5) has never been committed anywhere — it only ever goes into Fly secrets, per TEAM.md's approval contract, and is still pending the founder's own act of generating and setting it. |

No finding named a real external credential shape (a Fly API token, a
Supabase service-role key or JWT, a Postgres connection string with a
password, a GitHub PAT, a `.env` file). Cross-checked that directly: all
five secrets named in INBOX #2/#4/#5/#6 (`FILMRUNNER_DATABASE_URL`,
`FILMRUNNER_API_BEARER_TOKEN`, the Supabase service-role key, the VAPID
private key, the proposed `FILMRUNNER_CI_TOKEN`) are described in those
INBOX items as values to be set directly as Fly/GitHub Actions secrets,
never pasted into the repo or chat — this scan is consistent with that
contract having actually been followed, not just assumed.

## Failure-case handling

Both false-positive categories above are recorded here with the specific
reason they were dismissed, per this item's own failure case (never a
silent ignore, never a silent tool-wide ignore rule). No `.gitleaksignore`
or allowlist was added to the repo — the findings are real pattern
matches, just not real secrets, and dismissing them in this dated doc is
enough; adding a blanket ignore rule for `docs/research/*.json` would also
silently hide a genuine key if one were ever pasted into a future
Lighthouse artifact by accident.

No credential was found to have ever been committed, so no rotation is
needed and no new INBOX item is filed for this result.
