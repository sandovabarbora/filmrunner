"""Pydantic schemas for Web Push subscriptions and delivery summaries (FR-16)."""

from pydantic import BaseModel, Field, field_validator

from app.services.push import is_known_push_endpoint


class PushKeys(BaseModel):
    """The two keys `PushManager.subscribe()` returns, per the Web Push spec."""

    p256dh: str = Field(max_length=255)
    auth: str = Field(max_length=255)


class PushSubscriptionCreate(BaseModel):
    endpoint: str = Field(max_length=1000)
    keys: PushKeys
    link_url: str = Field(max_length=2000)

    @field_validator("endpoint")
    @classmethod
    def _endpoint_is_a_known_push_service(cls, value: str) -> str:
        if not is_known_push_endpoint(value):
            raise ValueError("endpoint must be an https URL on a known push service")
        return value


class VapidKeyRead(BaseModel):
    public_key: str | None


class DeliveryFailureRead(BaseModel):
    crew_member_name: str
    reason: str


class NotificationSummaryRead(BaseModel):
    attempted: int
    delivered: int
    failed: list[DeliveryFailureRead] = []
