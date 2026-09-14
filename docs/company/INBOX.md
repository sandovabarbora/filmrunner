# Inbox

Approval queue. Only the founder changes `state`. Grammar in TEAM.md.

## #1 · pm · Recruit and invite five Prague discovery interview candidates (FR-3)
- state: pending
- what: identify at least five real candidates (1st AD, 2nd AD, production coordinator; mixed production sizes) using the founder's network first and, if that doesn't reach five, the fallback channels in docs/research/discovery-plan.md (FAMU, Czech Film Commission listings, public filming-permit data), then send the draft invitation email from that plan to each of them
- why: BRIEF.md Q1-Q4 can only be answered by real interviews; this routine has no access to the founder's network and cannot name real people or send email to anyone but sandovabarb@gmail.com
- risk: outreach happens under the founder's own name and relationships in a small Prague film community — a bad first impression is hard to undo, so it must come from her, not an automated send
- proposal: founder names or confirms candidates (using the plan's fallback channels if needed) and sends the draft email herself in an interactive session; once interviews are scheduled, note it here and set this item's state so a future shift knows real discovery is under way

## #2 · tech-lead · Create/confirm Fly.io and Supabase accounts, set production secrets, deploy and seed (FR-8)
- state: done
- what: create or confirm a Fly.io account and the `filmrunner-api` app (region `fra`), and a Supabase project (Frankfurt) used as plain Postgres; set the Fly secrets `FILMRUNNER_DATABASE_URL` (Supabase session pooler, port 5432, `sslmode=require`), `FILMRUNNER_API_BEARER_TOKEN`, `FILMRUNNER_ENVIRONMENT=production`, `FILMRUNNER_CORS_ORIGINS=https://sandovabarbora.github.io`; run `cd backend && fly deploy`; then run `python -m app.seed_demo` once against production to load the demo call sheet (PR #24)
- why: the routine cannot create accounts, hold payment details, or deploy (TEAM.md approval contract); ADR-002 deliberately keeps deploy manual and founder-only so no deploy-capable token is stored in GitHub
- risk: Supabase's free tier pauses a project after a week of inactivity, which would silently break the live demo link; Fly's free allowance covers this app's size with scale-to-zero (a few seconds' cold start on the first request)
- proposal: founder does this once in an interactive session or from her machine per `docs/adr/ADR-002-hosting.md`; once deployed and seeded, note the live API URL and the seeded call sheet id here (or in STATUS.md) so a future shift can wire the GitHub Pages viewer's default link to it

## #3 · tech-lead · Custom SMTP for sign-in emails (Supabase built-in mailer is 2 emails/hour)
- state: pending
- what: create a transactional email account (Resend suggested: free tier 3,000/month; or Postmark), verify a sending domain or use their test sender, and enter host, port, user, password and sender address in Supabase → Authentication → SMTP Settings
- why: verified 2026-09-14: the built-in mailer refuses the third sign-in email within an hour ("Error sending magic link email") and Supabase documents it as non-production, best-effort; ADs sign in at 05:00 and cannot wait an hour
- risk: an account and possibly a domain DNS change; sender reputation if the domain is new
- proposal: founder creates the Resend account and pastes the SMTP credentials into Supabase directly (never into the repo or chat); the team then re-runs the code sign-in check and raises the Supabase auth rate limit to 30/h
