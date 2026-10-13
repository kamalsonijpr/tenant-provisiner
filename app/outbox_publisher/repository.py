from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.shared.models import OutboxEvent
from app.shared.time import utc_now


def fetch_unpublished_events(session: Session, *, limit: int = 100) -> list[OutboxEvent]:
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.created_at, OutboxEvent.id)
        .limit(limit)
    )
    return list(session.scalars(stmt))


list_unpublished_events = fetch_unpublished_events
select_unpublished_events = fetch_unpublished_events


def mark_events_published(session: Session, event_ids: Iterable[UUID]) -> int:
    ids = list(dict.fromkeys(event_ids))
    if not ids:
        return 0

    result = session.execute(
        update(OutboxEvent)
        .where(OutboxEvent.id.in_(ids), OutboxEvent.published_at.is_(None))
        .values(published_at=utc_now())
    )
    return int(result.rowcount or 0)


mark_rows_published = mark_events_published
