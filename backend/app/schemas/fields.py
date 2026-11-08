"""Validated input types. For Create and Update models only: stored rows predate them and must keep reading back."""

import re
from typing import Annotated

from pydantic import AfterValidator, Field

_CLOCK = re.compile(r"([0-9]{1,2})[:.,]([0-9]{2})")


def _clock_time(value: str | None) -> str | None:
    """The editor's time fields are free text, so "6:30" and the Czech "6.30" or "6,30" arrive as well as "06:30"; all become HH:MM."""
    if value is None or not value.strip():
        return None
    match = _CLOCK.fullmatch(value.strip())
    if match is None or int(match[1]) > 23 or int(match[2]) > 59:
        raise ValueError("must be a time from 00:00 to 23:59, like 06:30")
    return f"{int(match[1]):02d}:{match[2]}"


def _no_nul(value: str | None) -> str | None:
    # Postgres cannot store a NUL byte in text; the driver raises, which used to surface as a 500.
    if value is not None and "\x00" in value:
        raise ValueError("must not contain a NUL byte")
    return value


ClockTime = Annotated[str | None, AfterValidator(_clock_time)]


def text(max_length: int):
    return Annotated[str, Field(max_length=max_length), AfterValidator(_no_nul)]


def optional_text(max_length: int):
    return Annotated[str | None, Field(max_length=max_length), AfterValidator(_no_nul)]
