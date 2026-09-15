"""Run once, by a human, to generate the VAPID keypair for Web Push (FR-16).

Never run by the routine and never commits its output anywhere — prints the
two keys to the terminal so the founder can paste them directly into
`fly secrets set` (INBOX #5). See docs/adr/ADR-007-web-push-notifications.md.

Usage:
    cd backend && python -m scripts.generate_vapid_keys
"""

from app.services.push import generate_keypair


def main() -> None:
    public_key, private_key = generate_keypair()
    print("Public key  (FILMRUNNER_VAPID_PUBLIC_KEY):", public_key)
    print("Private key (FILMRUNNER_VAPID_PRIVATE_KEY):", private_key)
    print()
    print("Set both as Fly secrets, never commit them:")
    print("  fly secrets set -a filmrunner-api \\")
    print(f'    FILMRUNNER_VAPID_PUBLIC_KEY="{public_key}" \\')
    print(f'    FILMRUNNER_VAPID_PRIVATE_KEY="{private_key}"')


if __name__ == "__main__":
    main()
