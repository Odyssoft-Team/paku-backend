import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.db import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

# Tiempo máximo que una orden puede quedar en payment_status=verifying antes de
# escalar para revisión manual (ver plan de rediseño de pagos: punto de equilibrio
# entre darle margen al sistema y no perjudicar la experiencia del cliente).
_VERIFYING_ESCALATION_MINUTES = 20


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


async def _reconcile_verifying_payments_job() -> None:
    """
    Resuelve órdenes en payment_status=verifying: se intentó cobrar pero no se pudo
    confirmar el resultado a tiempo (ver PayOrder en orders/app/use_cases_impl/payment.py).
    Consulta a culqi-python si ya hay un resultado registrado; si sigue sin respuesta
    tras _VERIFYING_ESCALATION_MINUTES, la deja para revisión manual (no se fuerza a
    failed sin evidencia — podría haberse cobrado igual y decirle al cliente que no
    sería falso).
    """
    now = datetime.now(timezone.utc)

    try:
        async with AsyncSessionLocal() as session:
            from app.modules.orders.infra.postgres_order_repository import PostgresOrderRepository
            from app.modules.orders.infra.culqi_client import CulqiPythonClient
            from app.modules.orders.app.use_cases_impl.payment import (
                _notify_payment_confirmed,
                _payment_method_from_source_type,
            )
            from app.modules.notifications.infra.postgres_notification_repository import PostgresNotificationRepository
            from app.modules.notifications.app.use_cases import CreateNotification

            orders_repo = PostgresOrderRepository(session=session, engine=engine)
            culqi_client = CulqiPythonClient()

            verifying_orders = await orders_repo.list_verifying_orders()
            resolved = 0
            escalated = 0

            for order in verifying_orders:
                payments = await culqi_client.find_payments(order_id=str(order.id))

                if payments:
                    latest = payments[0]  # ya viene ordenado por created_at desc

                    if latest["status"] == "success":
                        payment_method = _payment_method_from_source_type(latest["source_type"])
                        paid_order = await orders_repo.confirm_payment(
                            id=order.id,
                            user_id=order.user_id,
                            culqi_charge_id=latest["culqi_charge_id"] or "",
                            payment_method=payment_method,
                        )
                        await _notify_payment_confirmed(orders_repo, paid_order)
                        resolved += 1
                        continue

                    if latest["status"] == "failed":
                        await orders_repo.fail_payment(id=order.id, user_id=order.user_id)
                        try:
                            notifications_repo = PostgresNotificationRepository(session=session, engine=engine)
                            await CreateNotification(repo=notifications_repo).execute(
                                user_id=order.user_id,
                                type="order_status",
                                title="No se pudo procesar tu pago",
                                body=(
                                    "Hubo un problema con tu método de pago y no se realizó "
                                    "ningún cobro. Por favor, intenta reservar de nuevo."
                                ),
                                data={"order_id": str(order.id), "payment_status": "failed"},
                            )
                        except Exception:
                            logger.exception(
                                "Failed to notify payment failure for order %s", order.id
                            )
                        resolved += 1
                        continue

                # Sigue ambiguo: culqi-python no respondió, o todavía no hay ningún
                # intento registrado. Se reintenta en la próxima corrida salvo que ya
                # se pasó el tiempo límite.
                age_minutes = (now - order.updated_at).total_seconds() / 60
                if age_minutes >= _VERIFYING_ESCALATION_MINUTES:
                    escalated += 1
                    logger.warning(
                        "reconcile_verifying_payments: order %s lleva %.0f min en "
                        "verifying sin resolución — requiere revisión manual",
                        order.id,
                        age_minutes,
                    )

            logger.info(
                "reconcile_verifying_payments_job checked=%s resolved=%s escalated=%s",
                len(verifying_orders),
                resolved,
                escalated,
            )
    except Exception:
        logger.exception("reconcile_verifying_payments_job failed")


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
    scheduler.add_job(
        _reconcile_verifying_payments_job,
        trigger=IntervalTrigger(minutes=5),
        id="reconcile_verifying_payments_job",
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
