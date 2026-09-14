# ADR-004: Sign-in with Supabase Auth, verified by JWKS

Date: 2026-09-14. Status: accepted (founder decision in session). Serves
FR-12; unblocks FR-13, FR-15, FR-16.

## Context

The editor asked an AD for an API URL and a bearer token. That is a
developer interface, not a product ("token na co? proč token a URL?").
The crew viewer stays public by link; the AD side needs identity.

## Options

1. Supabase Auth (email code or magic link), JWT verified in FastAPI
   against the project's JWKS. Configuration, not code; roles (FR-15) and
   personal links (FR-13) can hang off the user id.
2. A per-production secret link. No accounts, but no identity either:
   "who published REV B" stays unknown and roles are impossible.
3. Hand-rolled magic links in FastAPI plus an email provider. More code
   and one more service to run.

## Decision

Option 1. Verified against the current Supabase docs on 2026-09-14: this
project signs tokens with ES256; keys are served at
`<supabase_url>/auth/v1/.well-known/jwks.json`, cacheable for at most 10
minutes; the shared HS256 secret is discouraged and not used.

- Backend: `require_principal` accepts a Supabase JWT (ES256/RS256 via
  `PyJWKClient`, audience `authenticated`) or the service token (seed and
  tests only). `created_by` on a revision comes from the identity (user
  email, or `service:<name>`), never from the request body, which closes
  the last FR-7 finding.
- Editor: email → 6-digit code (primary, because a magic link opened from
  a mail app lands in Safari, not in the home-screen PWA) or the link.
  PKCE flow so tokens never sit in the URL hash the editor routes on.
  supabase-js keeps and refreshes the session on the phone.
- Build-time configuration, all public by design: `VITE_API_BASE`,
  `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` as GitHub Actions
  variables (the anon key is meant to ship in the bundle; it authorises
  nothing by itself). Fly secret `FILMRUNNER_SUPABASE_URL` tells the API
  where the JWKS lives.
- Without those variables (CI, local), the editor shows the old Connect
  screen for the service token; the end-to-end tests inject that
  connection through localStorage, so they run against both builds.
- Authorisation is still "any signed-in user may do anything"; per
  production roles are FR-15.

## Supabase project setup (founder, once)

1. Authentication → Providers → Email: enabled; "Confirm email" may stay on.
2. Authentication → Email Templates → Magic Link: include `{{ .Token }}`
   so the email carries the 6-digit code as well as the link.
3. Authentication → URL Configuration: Site URL
   `https://sandovabarbora.github.io/filmrunner/editor.html`; Redirect
   URLs add the same and `http://localhost:8080/editor.html`.
4. Project Settings → API: copy Project URL and anon public key into the
   GitHub variables above.

## Revisit when

A production needs SSO (then a second provider in Supabase, not a new
system), or the service token is still in use for anything but seeding.
