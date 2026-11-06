"""Web Push subscription endpoints (FR-16).

Unauthenticated by design, like the rest of the public call-sheet API: a
crew member subscribes from their own personal link on their own phone,
identified by the same unguessable personal_token FR-13 already uses for
read access, not by signing in. See docs/adr/ADR-007-web-push-notifications.md.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.production import CrewMember
from app.models.push import PushSubscription
from app.schemas.push import PushSubscriptionCreate, VapidKeyRead
from app.services import push as push_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Subscribing needs only a personal link, so without a cap one leaked link can grow the table and every publish's fan-out.
MAX_SUBSCRIPTIONS_PER_MEMBER = 5


@router.get("/public/push/vapid-key", response_model=VapidKeyRead)
def get_vapid_key() -> VapidKeyRead:
    """None until the founder sets the VAPID secrets (INBOX #5); the frontend
    reads this to decide whether to offer "Enable notifications" at all."""
    return VapidKeyRead(public_key=push_service.public_key())


def _crew_member_or_404(db: Session, token: str) -> CrewMember:
    member = db.query(CrewMember).filter(CrewMember.personal_token == token).first()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This personal link does not belong to a crew member")
    return member


def _evict_oldest_beyond_cap(db: Session, member: CrewMember, keep_endpoint: str) -> None:
    others = (
        db.query(PushSubscription)
        .filter(PushSubscription.crew_member_id == member.id, PushSubscription.endpoint != keep_endpoint)
        .order_by(PushSubscription.created_at.desc(), PushSubscription.id)
        .offset(MAX_SUBSCRIPTIONS_PER_MEMBER - 1)
        .all()
    )
    for subscription in others:
        db.delete(subscription)


@router.post("/public/crew/{token}/push-subscription", status_code=status.HTTP_201_CREATED)
def subscribe(token: str, payload: PushSubscriptionCreate, db: Session = Depends(get_db)) -> dict:
    member = _crew_member_or_404(db, token)
    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == payload.endpoint).first()
    if existing is not None:
        # Re-subscribing with the same endpoint (e.g. the browser refreshed
        # the encryption keys) updates in place rather than duplicating.
        existing.crew_member_id = member.id
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
        existing.link_url = payload.link_url
    else:
        db.add(
            PushSubscription(
                crew_member_id=member.id, endpoint=payload.endpoint,
                p256dh=payload.keys.p256dh, auth=payload.keys.auth, link_url=payload.link_url,
            )
        )
    _evict_oldest_beyond_cap(db, member, payload.endpoint)
    db.commit()
    logger.info("Push subscription saved for crew member %s", member.id)
    return {"status": "subscribed"}


@router.delete("/public/crew/{token}/push-subscription", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(token: str, endpoint: str, db: Session = Depends(get_db)) -> None:
    """`endpoint` as a query param: the one thing the browser can still tell
    us about a subscription it is about to drop."""
    member = _crew_member_or_404(db, token)
    db.query(PushSubscription).filter(
        PushSubscription.crew_member_id == member.id, PushSubscription.endpoint == endpoint
    ).delete()
    db.commit()
