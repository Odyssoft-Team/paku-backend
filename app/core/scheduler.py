import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.db import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=str(timezone.utc))
    return _scheduler


async def _cleanup_job() -> None:
    now = datetime.now(timezone.utc)

    try:
        async with AsyncSessionLocal() as session:
            from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository
            from app.modules.cart.infra.postgres_cart_repository import PostgresCartRepository

            holds_repo = PostgresHoldRepository(session=session, engine=engine)
            cart_repo = PostgresCartRepository(session=session, engine=engine)

            expired_holds = await holds_repo.expire_holds(now=now)
            expired_carts = await cart_repo.expire_carts(now=now)

            logger.info("cleanup_job expired_holds=%s expired_carts=%s", expired_holds, expired_carts)
    except Exception:
        logger.exception("cleanup_job failed")


def start_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        return

    scheduler.add_job(
        _cleanup_job,
        trigger=IntervalTrigger(minutes=5),
        id="cleanup_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("APScheduler started")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return

    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")

    _scheduler = None
