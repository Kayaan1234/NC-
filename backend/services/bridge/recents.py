"""Per-student memory of which topics were looked up for which step.

The rest of the bridge is deliberately global — one verdict, one pool and one
card per topic, shared by everyone, which is what makes the cache pay for itself.
This module owns the one exception, and it exists because a search that succeeded
previously had nowhere to go: a live run stores its verdict DRAFT, the shelf
serves PUBLISHED only, and the finder's progress panel unmounts the moment the
run stops being queued or running.

One function, called from three places, so the eviction rule is written once.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.models.Bridge import RECENT_SEARCH_LIMIT, BridgeRecentSearch
from backend.models.TrainingJob import utcnow

logger = logging.getLogger(__name__)


def record_search(
    db: Session,
    *,
    user_id: uuid.UUID,
    model_id: str,
    topic_slug: str,
    limit: int = RECENT_SEARCH_LIMIT,
    now: datetime | None = None,
) -> None:
    """Remember that this student looked up this topic for this step.

    Call only where a verdict already exists to link to. A search with no verdict
    behind it would render as a card that goes nowhere, and — worse — would
    evict a real result to do it.

    Re-searching a remembered topic bumps it to the head rather than duplicating
    it; that is what the unique constraint buys. Everything past `limit` is then
    deleted, so the table holds at most `limit` rows per (user, step) and "the
    fourth replaces the oldest" is true of storage, not just of the page.
    """
    stamp = now or utcnow()

    # ON CONFLICT rather than read-then-write: two tabs submitting the same topic
    # at once would otherwise race between the SELECT and the INSERT and trip the
    # unique constraint. The bump and the insert are the same statement.
    db.execute(
        pg_insert(BridgeRecentSearch)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            model_id=model_id,
            topic_slug=topic_slug,
            searched_at=stamp,
        )
        .on_conflict_do_update(
            constraint="uq_bridge_recent_user_model_topic",
            set_={"searched_at": stamp},
        )
    )

    # `id` breaks the tie on `searched_at`. Two searches inside the same clock
    # tick are not hypothetical — the tests make them on purpose — and without a
    # total order the keeper set is chosen differently on each execution, so the
    # wrong row gets evicted intermittently.
    keep = (
        select(BridgeRecentSearch.id)
        .where(
            BridgeRecentSearch.user_id == user_id,
            BridgeRecentSearch.model_id == model_id,
        )
        .order_by(BridgeRecentSearch.searched_at.desc(), BridgeRecentSearch.id.desc())
        .limit(limit)
        .scalar_subquery()
    )
    db.query(BridgeRecentSearch).filter(
        BridgeRecentSearch.user_id == user_id,
        BridgeRecentSearch.model_id == model_id,
        BridgeRecentSearch.id.notin_(keep),
    ).delete(synchronize_session=False)

    db.commit()


def record_search_quietly(db: Session, **kwargs) -> None:
    """`record_search`, but a failure is logged instead of raised.

    For the worker's call site only. By the time this runs the verdict is stored
    and the money is spent, so letting a bookkeeping write fail the job would
    throw away a real result to lose one list entry.

    The inner guard is not belt-and-braces. `database.reset_session` records that
    a session holding a dropped connection raises OperationalError *from
    rollback()* — and a rollback sitting bare in an `except` handler escapes the
    handler and killed the drain loop once already.
    """
    try:
        record_search(db, **kwargs)
    except Exception:                            # noqa: BLE001 - see docstring
        logger.exception("could not record recent search; the verdict is unaffected")
        try:
            db.rollback()
        except Exception:                        # noqa: BLE001 - see docstring
            logger.exception("rollback failed too; leaving the session for the drain to reset")
