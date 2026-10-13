from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def format_utc_millis(value: datetime) -> str:
    utc_value = value.astimezone(UTC)
    return utc_value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
