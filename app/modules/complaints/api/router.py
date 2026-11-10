"""Libro de Reclamaciones (feature 0022): registro público de hojas y gestión por el admin."""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_roles
from app.core.db import get_async_session
from app.core.rate_limiter import RateLimiter
from app.core.timezone import today_lima
from app.modules.complaints.api.schemas import (
    ComplaintAnswerIn,
    ComplaintDetailOut,
    ComplaintIn,
    ComplaintListOut,
    ComplaintReceiptOut,
    ComplaintSummaryOut,
    SheetRowOut,
)
from app.modules.complaints.app.use_cases import (
    AnswerComplaint,
    GetComplaint,
    ListComplaints,
    SubmitComplaint,
    sheet_rows,
)
from app.modules.complaints.domain.complaints import KINDS, RECEIVED, STATUSES
from app.modules.complaints.infra.models import ComplaintModel
from app.modules.complaints.infra.postgres_complaint_repository import PostgresComplaintRepository
from app.modules.general_settings.infra.postgres_settings_repository import PostgresSettingsRepository
from app.modules.messaging.app.sender import send_email

router = APIRouter(prefix="/complaints", tags=["complaints"])
admin_router = APIRouter(prefix="/complaints", tags=["complaints-admin"])

# Holgado a propósito: es un canal legal del consumidor; solo frena envíos automáticos.
submit_limiter = RateLimiter(max_failures=20, window_seconds=3600, lockout_seconds=3600)


def get_repo(session: AsyncSession = Depends(get_async_session)) -> PostgresComplaintRepository:
    return PostgresComplaintRepository(session=session)


def get_notifier(session: AsyncSession = Depends(get_async_session)):
    async def notify(**kw: Any) -> Any:
        return await send_email(session, **kw)
    return notify


def _summary(c: ComplaintModel) -> dict[str, Any]:
    return dict(
        id=c.id, code=c.code, created_at=c.created_at, kind=c.kind, kind_label=KINDS.get(c.kind, c.kind),
        consumer_name=c.consumer_name, email=c.email, status=c.status, status_label=STATUSES.get(c.status, c.status),
        response_due=c.response_due, overdue=c.status == RECEIVED and today_lima() > c.response_due,
    )


def _detail(c: ComplaintModel) -> ComplaintDetailOut:
    return ComplaintDetailOut(
        **_summary(c), sheet=[SheetRowOut(label=k, value=v) for k, v in sheet_rows(c)], response=c.response,
        responded_at=c.responded_at, responded_by=c.responded_by,
    )


@router.post("", response_model=ComplaintReceiptOut, status_code=status.HTTP_201_CREATED)
async def submit_complaint(
    payload: ComplaintIn,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    repo: PostgresComplaintRepository = Depends(get_repo),
    notify=Depends(get_notifier),
) -> ComplaintReceiptOut:
    """
    Registra una hoja del Libro de Reclamaciones (sin sesión). Asigna el correlativo del año (`LR-2026-000001`),
    calcula el plazo de respuesta (15 días hábiles) y envía la copia al correo del consumidor y un aviso al correo
    de reclamos de la empresa. 422 `COMPLAINT_INVALID` con `field` si algo no es válido.
    """
    ip = request.client.host if request.client else "unknown"
    submit_limiter.check(ip)
    use_case = SubmitComplaint(repo=repo, settings_repo=PostgresSettingsRepository(session=session), notify=notify)
    complaint = await use_case.execute(payload.model_dump())
    submit_limiter.record_failure(ip)  # cuenta envíos, no fallas
    return ComplaintReceiptOut(
        id=complaint.id, code=complaint.code, created_at=complaint.created_at, response_due=complaint.response_due,
        email=complaint.email, provider_legal_name=complaint.provider_legal_name,
        provider_ruc=complaint.provider_ruc, provider_address=complaint.provider_address,
    )


@admin_router.get("", response_model=ComplaintListOut)
async def list_complaints(
    status_: Optional[str] = Query(None, alias="status", description="received | answered"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresComplaintRepository = Depends(get_repo),
) -> ComplaintListOut:
    """Hojas del Libro de Reclamaciones, de la más reciente a la más antigua."""
    items, total = await ListComplaints(repo=repo).execute(
        status=status_ if status_ in STATUSES else None, limit=limit, offset=offset)
    return ComplaintListOut(items=[ComplaintSummaryOut(**_summary(c)) for c in items], total=total)


@admin_router.get("/{complaint_id}", response_model=ComplaintDetailOut)
async def get_complaint(
    complaint_id: UUID,
    _: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresComplaintRepository = Depends(get_repo),
) -> ComplaintDetailOut:
    """Hoja completa y su respuesta. 404 `COMPLAINT_NOT_FOUND`."""
    return _detail(await GetComplaint(repo=repo).execute(complaint_id))


@admin_router.post("/{complaint_id}/answer", response_model=ComplaintDetailOut)
async def answer_complaint(
    complaint_id: UUID,
    payload: ComplaintAnswerIn,
    current: CurrentUser = Depends(require_roles("admin")),
    repo: PostgresComplaintRepository = Depends(get_repo),
    notify=Depends(get_notifier),
) -> ComplaintDetailOut:
    """
    Registra la respuesta (una sola vez) y la envía al correo del consumidor. 409 `COMPLAINT_ALREADY_ANSWERED`;
    422 `COMPLAINT_INVALID` si la respuesta es muy corta o muy larga.
    """
    complaint = await AnswerComplaint(repo=repo, notify=notify).execute(complaint_id, payload.response,
                                                                       actor_id=current.id)
    return _detail(complaint)
