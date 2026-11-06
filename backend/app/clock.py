"""The product's clock. Crews and shoots are in Prague, so "today" is Prague's date wherever the server runs."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

PRAGUE = ZoneInfo("Europe/Prague")


def prague_now() -> datetime:
    return datetime.now(PRAGUE)


def prague_today() -> date:
    return prague_now().date()
