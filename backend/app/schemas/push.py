"""Pydantic schemas for Web Push subscriptions and delivery summaries (FR-16)."""

from pydantic import BaseModel


class PushKeys(BaseModel):
    """The two keys `PushManager.subscribe()` returns, per the Web Push spec."""

    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    endpoint: str
    keys: PushKeys
    link_url: str


class VapidKeyRead(BaseModel):
    public_key: str | None


class DeliveryFailureRead(BaseModel):
    crew_member_name: str
    reason: str


class NotificationSummaryRead(BaseModel):
    attempted: int
    delivered: int
    failed: list[DeliveryFailureRead] = []
