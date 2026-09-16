## What and why

<!-- one paragraph; link the BACKLOG item (FR-n) -->

## Gates

Full checklist: [docs/gates/pre-merge-checklist.md](../docs/gates/pre-merge-checklist.md)
(see also docs/company/TEAM.md). Tick each box, or leave it unchecked with
a one-line reason if it does not apply.

- [ ] Tests cover the change, including one failure case
- [ ] No secrets, tokens, or personal data added
- [ ] Every non-public route requires auth
- [ ] Input is validated; audit fields (`created_by`, `published_at`, ...) are server-set
- [ ] New/bumped dependencies are pinned to an exact version
- [ ] `python scripts/check_company_docs.py` is clean
- [ ] CI is green on this PR's own head
- [ ] Nothing here sends, spends, publishes, or deploys without an approved INBOX item
