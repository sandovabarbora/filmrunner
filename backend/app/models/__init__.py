"""Import every model module so SQLAlemy's declarative registry sees all
mapped classes before `configure_mappers()` / `Base.metadata.create_all()`
resolves string-quoted relationship targets (e.g. Mapped["CallSheet"]).

Reference: https://docs.sqlalchemy.org/en/20/orm/mapping_api.html#sqlalchemy.orm.configure_mappers
"""

from app.models.call_sheet import (  # noqa: F401
    CallSheet,
    CallSheetRevision,
    CastCallEntry,
    CrewCallEntry,
    DistributionLog,
    ScheduleItem,
)
from app.models.membership import ProductionMember, ProductionRole  # noqa: F401
from app.models.production import CastMember, Contact, ContactPhoto, CrewMember, Location, Production  # noqa: F401
from app.models.push import PushSubscription  # noqa: F401

__all__ = [
    "Production",
    "Contact",
    "Location",
    "CrewMember",
    "CastMember",
    "CallSheet",
    "CallSheetRevision",
    "ScheduleItem",
    "CastCallEntry",
    "CrewCallEntry",
    "DistributionLog",
    "ProductionMember",
    "ContactPhoto",
    "ProductionRole",
    "PushSubscription",
]
