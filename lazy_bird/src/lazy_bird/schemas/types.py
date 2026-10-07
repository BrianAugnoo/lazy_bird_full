"""Field types shared by the API schemas."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


# Timestamps are stored in UTC, but SQLite returns them without a timezone: this
# type makes the API always send them with an explicit offset ("...+00:00").
UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]
