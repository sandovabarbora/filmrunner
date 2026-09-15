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

## #4 · tech-lead · Create the Supabase Storage `avatars` bucket and set the service-role key (FR-18)
- state: pending
- what: in the Supabase dashboard, create a Storage bucket named `avatars` (public read) in the same project used for Postgres and auth; copy the project's service-role key and set it as the Fly secret `FILMRUNNER_SUPABASE_SERVICE_ROLE_KEY` (`fly secrets set -a filmrunner-api FILMRUNNER_SUPABASE_SERVICE_ROLE_KEY=...`); `FILMRUNNER_SUPABASE_URL` is already set from INBOX #2
- why: PR #48 (FR-18 photo upload) is code-complete — `POST /contacts/{id}/photo` uploads a 256px-resized avatar and stores its public URL — but the bucket and service-role key don't exist yet, so the endpoint correctly 503s with "Photo upload is not configured yet" on every attempt; the routine cannot create Supabase resources or hold the service-role key (TEAM.md)
- risk: the service-role key bypasses Storage row-level security entirely — it must go into Fly secrets only, never the repo or chat; a public-read bucket means anyone with a guessed/leaked URL can view an avatar (acceptable for a crew photo, not for anything sensitive)
- proposal: founder does this once from the Supabase dashboard and `fly secrets set`; once set, the feature works immediately with no further deploy (the code already reads the setting from `app/config.py`) — a future shift can verify by uploading a real photo against the live API and confirming it appears on a published sheet

## #5 · tech-lead · Generate and set the VAPID keypair for Web Push (FR-16)
- state: pending
- what: run `cd backend && python -m scripts.generate_vapid_keys` once (locally or in an interactive session — never in the routine) and set the two printed values as Fly secrets: `fly secrets set -a filmrunner-api FILMRUNNER_VAPID_PUBLIC_KEY=... FILMRUNNER_VAPID_PRIVATE_KEY=...`; optionally also set `FILMRUNNER_VAPID_SUBJECT` to a `mailto:` address of the founder's choosing (defaults to a generic placeholder if left unset)
- why: PR #53 (FR-16 Web Push, branch feat/fr-16-push-notifications) is code-complete — subscribe/unsubscribe, the publish-time send, and the delivery-failure log all work — but with no VAPID keys configured `GET /api/v1/public/push/vapid-key` correctly returns `{"public_key": null}` and the editor never offers "Enable notifications" to any crew member; no account or payment is needed (VAPID is a self-issued keypair, not a third-party service), only the founder's own act of generating and storing it, since the routine must never hold or set Fly secrets (TEAM.md)
- risk: the private key can sign push messages as this server's identity — it must go into Fly secrets only, never the repo or chat; losing it just means generating a new pair (every existing browser subscription then needs to re-subscribe, since the old public key it was minted against no longer matches)
- proposal: founder runs the script once and sets both secrets; once set, the feature works immediately with no further deploy (the code already reads the setting from `app/config.py`) — a future shift can verify by opening a personal crew link on a real phone, enabling notifications, and publishing a revision from another device (protocol: `docs/research/manual-test-protocol-push-ios.md`)
