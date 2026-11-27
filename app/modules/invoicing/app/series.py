"""Series de comprobantes (feature 0023): una activa por tipo; el correlativo nunca baja ni repite.

El siguiente número es el mayor entre el inicial configurado, el último emitido aquí + 1 (en el ambiente actual) y el
que propone Intifact. Así, si otro sistema usó la misma serie, basta con poner su último número + 1 como inicial.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException

from app.modules.invoicing.app.config import current_environment, invalid
from app.modules.invoicing.domain.intifact import NOMBRE_TIPO, TIPO_DOC, InvoicingInvalid, normalize_series
from app.modules.invoicing.infra.models import InvoicingSeriesModel, utcnow


@dataclass(frozen=True)
class SeriesView:
    id: UUID
    type: str                 # BOLETA | FACTURA
    doc_type: str             # 03 | 01
    series: str
    first_number: int
    is_active: bool
    issued: int               # en el ambiente actual
    last_number: Optional[int]
    next_number: int


async def series_view(repo, s: InvoicingSeriesModel, environment: Optional[str] = None) -> SeriesView:
    environment = environment or await current_environment(repo)
    issued, last = await repo.series_usage(s.series, environment)
    return SeriesView(id=s.id, type=NOMBRE_TIPO[s.doc_type], doc_type=s.doc_type, series=s.series,
                      first_number=s.first_number, is_active=s.is_active, issued=issued, last_number=last,
                      next_number=max(s.first_number, (last or 0) + 1))


async def local_next_number(repo, s: InvoicingSeriesModel, environment: str) -> int:
    _, last = await repo.series_usage(s.series, environment)
    return max(s.first_number, (last or 0) + 1)


async def active_series(repo, tipo: str) -> InvoicingSeriesModel:
    s = await repo.active_series(TIPO_DOC[tipo])
    if s is None:
        nombre = "boletas" if tipo == "BOLETA" else "facturas"
        raise HTTPException(status_code=409, detail={
            "code": "SERIES_NOT_CONFIGURED",
            "message": f"Falta configurar la serie de {nombre} (Facturación electrónica → Series)."})
    return s


async def _deactivate_others(repo, s: InvoicingSeriesModel) -> None:
    for other in await repo.other_series(s.doc_type, s.id):
        if other.is_active:
            other.is_active = False
            other.updated_at = utcnow()
            repo.session.add(other)


async def _ensure_unique(repo, code: str, except_id: Optional[UUID] = None) -> None:
    other = await repo.series_by_code(code)
    if other is not None and other.id != except_id:
        raise HTTPException(status_code=409, detail={"code": "SERIES_EXISTS", "message": f"La serie {code} ya existe."})


@dataclass
class ListSeries:
    repo: Any

    async def execute(self) -> list[SeriesView]:
        environment = await current_environment(self.repo)
        return [await series_view(self.repo, s, environment) for s in await self.repo.list_series()]


@dataclass
class CreateSeries:
    repo: Any

    async def execute(self, *, tipo: str, series: str, first_number: int, is_active: bool) -> SeriesView:
        doc_type = TIPO_DOC[tipo]
        try:
            code = normalize_series(series, doc_type)
        except InvoicingInvalid as exc:
            raise invalid(exc) from exc
        await _ensure_unique(self.repo, code)
        s = InvoicingSeriesModel(doc_type=doc_type, series=code, first_number=first_number, is_active=is_active)
        self.repo.session.add(s)
        await self.repo.session.flush()
        if s.is_active:
            await _deactivate_others(self.repo, s)
        await self.repo.commit()
        return await series_view(self.repo, s)


@dataclass
class UpdateSeries:
    repo: Any

    async def execute(self, series_id: UUID, *, series: Optional[str], first_number: Optional[int],
                      is_active: Optional[bool]) -> SeriesView:
        s = await self.repo.get_series(series_id)
        if s is None:
            raise HTTPException(status_code=404, detail={"code": "SERIES_NOT_FOUND", "message": "Serie no encontrada."})
        if series is not None:
            try:
                code = normalize_series(series, s.doc_type)
            except InvoicingInvalid as exc:
                raise invalid(exc) from exc
            if code != s.series:
                if await self.repo.series_used(s.series):
                    raise HTTPException(status_code=409, detail={
                        "code": "SERIES_IN_USE",
                        "message": "Esta serie ya tiene comprobantes emitidos: no se renombra. Crea una serie nueva."})
                await _ensure_unique(self.repo, code, except_id=s.id)
                s.series = code
        if first_number is not None:
            s.first_number = first_number
        if is_active is not None:
            s.is_active = is_active
            if is_active:
                await _deactivate_others(self.repo, s)
        s.updated_at = utcnow()
        self.repo.session.add(s)
        await self.repo.commit()
        return await series_view(self.repo, s)
