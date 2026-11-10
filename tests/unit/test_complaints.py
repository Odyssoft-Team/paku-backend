"""Feature 0022: Libro de Reclamaciones (validación, correlativo, plazo, copia por correo y respuesta).
SQLite en memoria; notificador falso (sin red)."""
import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.base import Base
from app.modules.complaints.app.use_cases import AnswerComplaint, ListComplaints, SubmitComplaint
from app.modules.complaints.domain.complaints import ComplaintInvalid, add_business_days, format_code, validate
from app.modules.complaints.infra.models import ComplaintCounterModel, ComplaintModel
from app.modules.complaints.infra.postgres_complaint_repository import PostgresComplaintRepository
from app.modules.general_settings.infra.models import GeneralSettingModel
from app.modules.general_settings.infra.postgres_settings_repository import PostgresSettingsRepository

T0 = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)  # lunes 10:00 en Lima
ADMIN = uuid4()

VALID = {
    "consumer_name": "  Ana   Pérez Quispe ", "doc_type": "DNI", "doc_number": "12345678",
    "email": "Ana@Correo.pe", "phone": "987 654 321", "item_type": "servicio",
    "item_description": "Baño Fresco y Limpio", "order_reference": "ORD-123", "amount_claimed": "75",
    "kind": "reclamo", "detail": "El servicio llegó dos horas tarde.", "request": "Devolución parcial.",
}


def _run(coro):
    return asyncio.run(coro)


class Notifier:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    async def __call__(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise RuntimeError("sin base de logs")


async def _ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[
            ComplaintModel.__table__, ComplaintCounterModel.__table__, GeneralSettingModel.__table__])
    session = async_sessionmaker(engine, expire_on_commit=False)()
    return SimpleNamespace(engine=engine, session=session, repo=PostgresComplaintRepository(session=session),
                           settings=PostgresSettingsRepository(session=session))


async def _close(ctx):
    await ctx.session.close()
    await ctx.engine.dispose()


# ── dominio ──────────────────────────────────────────────────────────────────

def test_validate_normalizes():
    data = validate(VALID)
    assert data.consumer_name == "Ana Pérez Quispe"
    assert (data.doc_type, data.email, data.amount_claimed) == ("dni", "ana@correo.pe", Decimal("75.00"))
    assert data.guardian_name is None


@pytest.mark.parametrize("change,field", [
    ({"consumer_name": ""}, "consumer_name"),
    ({"doc_type": "licencia"}, "doc_type"),
    ({"doc_number": "1234567"}, "doc_number"),            # DNI de 7 dígitos
    ({"doc_type": "ruc", "doc_number": "12345678"}, "doc_number"),
    ({"email": "ana@correo"}, "email"),
    ({"phone": "abc"}, "phone"),
    ({"is_minor": True}, "guardian_name"),
    ({"item_type": "otro"}, "item_type"),
    ({"amount_claimed": "-5"}, "amount_claimed"),
    ({"amount_claimed": "diez"}, "amount_claimed"),
    ({"kind": "sugerencia"}, "kind"),
    ({"detail": "corto"}, "detail"),
    ({"request": ""}, "request"),
])
def test_validate_rejects(change, field):
    with pytest.raises(ComplaintInvalid) as exc:
        validate({**VALID, **change})
    assert exc.value.field == field


def test_business_days_skip_weekends():
    assert add_business_days(date(2026, 11, 9), 15) == date(2026, 11, 30)   # lunes → lunes, 3 semanas
    assert add_business_days(date(2026, 11, 13), 1) == date(2026, 11, 16)   # viernes → lunes
    assert format_code(2026, 7) == "LR-2026-000007"


# ── casos de uso ─────────────────────────────────────────────────────────────

def test_submit_numbers_snapshots_and_notifies():
    async def scenario():
        ctx = await _ctx()
        try:
            notify = Notifier()
            submit = SubmitComplaint(repo=ctx.repo, settings_repo=ctx.settings, notify=notify, now=lambda: T0)
            first = await submit.execute(VALID)
            second = await submit.execute({**VALID, "kind": "queja", "amount_claimed": None})
            assert (first.code, second.code) == ("LR-2026-000001", "LR-2026-000002")
            assert first.response_due == date(2026, 11, 30)
            assert (first.provider_legal_name, first.provider_ruc) == ("SMARTPETSOLUTIONS S.A.C.", "20615013898")
            assert "San Borja" in first.provider_address
            # copia al consumidor y aviso a la empresa por cada hoja
            assert [c["to"] for c in notify.calls[:2]] == ["ana@correo.pe", "admin@paku.com.pe"]
            assert notify.calls[0]["idempotency_key"] == f"complaint:copy:{first.id}"
            assert "LR-2026-000001" in notify.calls[0]["text"] and "INDECOPI" in notify.calls[0]["text"]
            items, total = await ListComplaints(repo=ctx.repo).execute(status="received", limit=10, offset=0)
            assert total == 2
        finally:
            await _close(ctx)
    _run(scenario())


def test_submit_escapes_html_and_survives_notifier_failure():
    async def scenario():
        ctx = await _ctx()
        try:
            notify = Notifier(fail=True)
            submit = SubmitComplaint(repo=ctx.repo, settings_repo=ctx.settings, notify=notify, now=lambda: T0)
            c = await submit.execute({**VALID, "detail": "<script>alert(1)</script> llegó tarde"})
            assert c.code == "LR-2026-000001"            # la hoja queda aunque falle el correo
            assert "<script>" not in notify.calls[0]["html"]
        finally:
            await _close(ctx)
    _run(scenario())


def test_submit_invalid_is_422_and_does_not_consume_number():
    async def scenario():
        ctx = await _ctx()
        try:
            submit = SubmitComplaint(repo=ctx.repo, settings_repo=ctx.settings, notify=Notifier(), now=lambda: T0)
            with pytest.raises(HTTPException) as exc:
                await submit.execute({**VALID, "email": "x"})
            assert exc.value.status_code == 422 and exc.value.detail["field"] == "email"
            assert (await submit.execute(VALID)).code == "LR-2026-000001"
        finally:
            await _close(ctx)
    _run(scenario())


def test_answer_once_and_email_consumer():
    async def scenario():
        ctx = await _ctx()
        try:
            notify = Notifier()
            c = await SubmitComplaint(repo=ctx.repo, settings_repo=ctx.settings, notify=notify,
                                      now=lambda: T0).execute(VALID)
            answer = AnswerComplaint(repo=ctx.repo, notify=notify, now=lambda: T0)
            with pytest.raises(HTTPException) as short:
                await answer.execute(c.id, "ok", actor_id=ADMIN)
            assert short.value.status_code == 422
            done = await answer.execute(c.id, "Te devolvemos S/ 22.50 en 2 días hábiles.", actor_id=ADMIN)
            assert (done.status, done.responded_by) == ("answered", ADMIN)
            assert notify.calls[-1]["to"] == "ana@correo.pe"
            assert notify.calls[-1]["idempotency_key"] == f"complaint:answer:{c.id}"
            with pytest.raises(HTTPException) as again:
                await answer.execute(c.id, "Otra respuesta distinta.", actor_id=ADMIN)
            assert again.value.status_code == 409
            with pytest.raises(HTTPException) as missing:
                await answer.execute(uuid4(), "Respuesta para nadie.", actor_id=ADMIN)
            assert missing.value.status_code == 404
        finally:
            await _close(ctx)
    _run(scenario())
