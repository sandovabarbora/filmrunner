"""Who gets told about a new revision, and what it says (FR-16).

Separate from app/services/push.py (the transport) so the message and the
audience — the actual product decision — are not buried inside a
send-a-message function. See docs/adr/ADR-007-web-push-notifications.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.call_sheet import CallSheet, CallSheetRevision, DistributionChannel, DistributionLog
from app.models.production import CrewMember
from app.models.push import PushSubscription
from app.services.call_sheets import change_summary, revision_changes
from app.services.push import PushDeliveryError, is_configured, send

logger = logging.getLogger(__name__)


@dataclass
class DeliveryFailure:
    crew_member_name: str
    reason: str


@dataclass
class NotificationSummary:
    attempted: int = 0
    delivered: int = 0
    failed: list[DeliveryFailure] = field(default_factory=list)


def _revision_message(call_sheet: CallSheet, revision: CallSheetRevision) -> tuple[str, str]:
    """(title, body) for the push notification — the same line FR-11 shows on the sheet itself."""
    title = f"Day {call_sheet.day_number}: REV {revision.revision_letter}"
    call = revision.general_crew_call or "call time not set"
    if revision.revision_letter == "A":
        body = f"New call sheet: crew call {call}"
    else:
        prev_letter = chr(ord(revision.revision_letter) - 1)
        prev = next((r for r in call_sheet.revisions if r.revision_letter == prev_letter), None)
        # The same diff the sheet shows (FR-23), so the push never says something the link does not.
        body = f"REV {revision.revision_letter} replaces {prev_letter}: {change_summary(revision_changes(prev, revision))}"
    return title, body


def notify_subscribers(db: Session, call_sheet: CallSheet, revision: CallSheetRevision) -> NotificationSummary:
    """Push the new revision to every subscribed crew member of this production.

    Every attempt — success or failure — is logged to DistributionLog so an
    AD can see who did not get the update (the dod's failure case), rather
    than assuming a push that returned 200 to *pywebpush* means a phone
    actually buzzed. When push is not configured (INBOX #5 not done yet)
    this is a no-op: an empty summary, not an error, since a production
    with no subscribers yet (nobody has opted in) looks identical.
    """
    summary = NotificationSummary()
    if not is_configured():
        return summary

    subscriptions = (
        db.query(PushSubscription)
        .join(CrewMember, CrewMember.id == PushSubscription.crew_member_id)
        .filter(CrewMember.production_id == call_sheet.production_id)
        .all()
    )
    if not subscriptions:
        return summary

    title, body = _revision_message(call_sheet, revision)

    for subscription in subscriptions:
        summary.attempted += 1
        member = subscription.crew_member
        payload = {"title": title, "body": body, "url": subscription.link_url, "tag": f"filmrunner-{call_sheet.id}"}
        try:
            send(endpoint=subscription.endpoint, p256dh=subscription.p256dh, auth=subscription.auth, payload=payload)
        except PushDeliveryError as exc:
            summary.failed.append(DeliveryFailure(crew_member_name=member.contact.name, reason=exc.reason))
            db.add(
                DistributionLog(
                    revision_id=revision.id, contact_id=member.contact_id, channel=DistributionChannel.PUSH,
                    sent_at=None, error=exc.reason,
                )
            )
            if exc.gone:
                # The browser itself revoked this subscription; stop retrying it.
                db.delete(subscription)
        else:
            summary.delivered += 1
            db.add(
                DistributionLog(
                    revision_id=revision.id, contact_id=member.contact_id, channel=DistributionChannel.PUSH,
                    sent_at=datetime.now(timezone.utc), error=None,
                )
            )

    db.commit()
    logger.info(
        "Notified %d/%d subscribers for revision %s of call sheet %s",
        summary.delivered, summary.attempted, revision.revision_letter, call_sheet.id,
    )
    return summary
