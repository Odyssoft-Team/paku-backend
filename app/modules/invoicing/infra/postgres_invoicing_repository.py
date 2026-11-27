"""Persistencia de facturación electrónica (feature 0023). Lee órdenes, usuarios y mascotas de otros módulos; solo
escribe en sus propias tablas."""
from __future__ import annotations

from datetime import date
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import Integer, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.invoicing.domain.intifact import FINALES, NO_VIGENTES, TRIGGER_PAYMENT, TRIGGER_SERVICE
from app.modules.invoicing.infra.models import (
    InvoiceDocumentModel,
    InvoicingCompanyModel,
    InvoicingProviderModel,
    InvoicingSeriesModel,
)

D = InvoiceDocumentModel


class PostgresInvoicingRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def _all(self, stmt) -> list:
        return list((await self._session.execute(stmt)).scalars().all())

    async def commit(self) -> None:
        await self._session.commit()

    async def save(self, model):
        self._session.add(model)
        await self._session.commit()
        return model

    # ---------- Proveedor ----------

    async def get(self, provider: str) -> Optional[InvoicingProviderModel]:
        return await self._session.get(InvoicingProviderModel, provider)

    # ---------- Series ----------

    async def list_series(self) -> list[InvoicingSeriesModel]:
        S = InvoicingSeriesModel
        return await self._all(select(S).order_by(S.doc_type.desc(), S.series))

    async def get_series(self, series_id: UUID) -> Optional[InvoicingSeriesModel]:
        return await self._session.get(InvoicingSeriesModel, series_id)

    async def series_by_code(self, code: str) -> Optional[InvoicingSeriesModel]:
        S = InvoicingSeriesModel
        return (await self._session.execute(select(S).where(S.series == code))).scalars().first()

    async def active_series(self, doc_type: str) -> Optional[InvoicingSeriesModel]:
        S = InvoicingSeriesModel
        return (await self._session.execute(
            select(S).where(S.doc_type == doc_type, S.is_active.is_(True)))).scalars().first()

    async def other_series(self, doc_type: str, except_id: UUID) -> list[InvoicingSeriesModel]:
        S = InvoicingSeriesModel
        return await self._all(select(S).where(S.doc_type == doc_type, S.id != except_id))

    async def series_usage(self, series: str, environment: str) -> tuple[int, Optional[int]]:
        """Emitidos con la serie en el ambiente y el mayor correlativo."""
        count, last = (await self._session.execute(
            select(func.count(D.id), func.max(cast(D.number, Integer))).where(
                D.series == series, D.environment == environment))).one()
        return int(count or 0), (int(last) if last is not None else None)

    async def series_used(self, series: str) -> bool:
        return (await self._session.execute(select(D.id).where(D.series == series).limit(1))).first() is not None

    # ---------- Comprobantes ----------

    async def get_document(self, document_id: UUID) -> Optional[InvoiceDocumentModel]:
        return await self._session.get(InvoiceDocumentModel, document_id)

    async def document_by_provider_id(self, provider_id: str) -> Optional[InvoiceDocumentModel]:
        return (await self._session.execute(select(D).where(D.provider_id == provider_id))).scalars().first()

    async def document_by_number(self, series: str, number: str, doc_type: Optional[str]) -> Optional[InvoiceDocumentModel]:
        stmt = select(D).where(D.series == series, D.number == number)
        if doc_type:
            stmt = stmt.where(D.doc_type == doc_type)
        return (await self._session.execute(stmt.order_by(D.created_at.desc()))).scalars().first()

    async def valid_document_for_order(self, order_id: UUID) -> Optional[InvoiceDocumentModel]:
        return (await self._session.execute(
            select(D).where(D.order_id == order_id, D.status.not_in(NO_VIGENTES)))).scalars().first()

    async def documents_for_order(self, order_id: UUID) -> list[InvoiceDocumentModel]:
        return await self._all(select(D).where(D.order_id == order_id).order_by(D.created_at.desc()))

    async def documents_in_progress(self, limit: int = 100) -> list[InvoiceDocumentModel]:
        return await self._all(select(D).where(D.status.not_in(FINALES), D.provider_id.is_not(None))
                               .order_by(D.created_at).limit(limit))

    async def documents_with_status(self, status: str) -> list[InvoiceDocumentModel]:
        return await self._all(select(D).where(D.status == status))

    async def accepted_not_notified(self, limit: int = 50) -> list[InvoiceDocumentModel]:
        return await self._all(select(D).where(D.status == "ACEPTADO", D.customer_notified_at.is_(None),
                                               D.customer_email.is_not(None)).order_by(D.created_at).limit(limit))

    def _registry_filters(self, *, doc_type, status, date_from, date_to, q, environment) -> list:
        f = []
        if environment:
            f.append(D.environment == environment)
        if doc_type:
            f.append(D.doc_type == doc_type)
        if status == "PENDIENTE":
            f.append(D.status.not_in(NO_VIGENTES | {"ACEPTADO"}))
        elif status == "FALLIDO":
            f.append(D.status.in_(NO_VIGENTES))
        elif status:
            f.append(D.status == status)
        if date_from:
            f.append(D.issue_date >= date_from)
        if date_to:
            f.append(D.issue_date <= date_to)
        if q and q.strip():
            pattern = f"%{q.strip()}%"
            f.append(or_(D.customer_name.ilike(pattern), D.customer_doc_number.ilike(pattern),
                         (D.series + "-" + D.number).ilike(pattern)))
        return f

    async def registry(self, *, doc_type: Optional[str], status: Optional[str], date_from: Optional[date],
                       date_to: Optional[date], q: Optional[str], environment: Optional[str], page: int,
                       page_size: int) -> tuple[list[InvoiceDocumentModel], int, float]:
        f = self._registry_filters(doc_type=doc_type, status=status, date_from=date_from, date_to=date_to, q=q,
                                   environment=environment)
        total = (await self._session.execute(select(func.count()).select_from(D).where(*f))).scalar_one()
        accepted = (await self._session.execute(
            select(func.coalesce(func.sum(D.total), 0)).where(*f, D.status == "ACEPTADO"))).scalar_one()
        rows = await self._all(select(D).where(*f).order_by(D.created_at.desc())
                               .offset((page - 1) * page_size).limit(page_size))
        return rows, int(total), float(accepted or 0)

    async def documents_between(self, start: date, end: date, environment: str, statuses: Iterable[str],
                                doc_types: Optional[Iterable[str]] = None) -> list[InvoiceDocumentModel]:
        stmt = select(D).where(D.issue_date >= start, D.issue_date <= end, D.environment == environment,
                               D.status.in_(list(statuses)))
        if doc_types:
            stmt = stmt.where(D.doc_type.in_(list(doc_types)))
        return await self._all(stmt.order_by(D.issue_date, D.doc_type, D.series, cast(D.number, Integer)))

    async def documents_in_environment(self, environment: str, statuses: Iterable[str]) -> list[InvoiceDocumentModel]:
        return await self._all(select(D).where(D.environment == environment, D.status.in_(list(statuses))))

    async def history_by_doc(self, numbers: set[str]) -> list[tuple]:
        """(número de documento, tipo, cantidad, total, último) de los aceptados."""
        if not numbers:
            return []
        stmt = (select(D.customer_doc_number, D.doc_type, func.count(), func.sum(D.total), func.max(D.issue_date))
                .where(D.customer_doc_number.in_(numbers), D.status == "ACEPTADO")
                .group_by(D.customer_doc_number, D.doc_type))
        return list((await self._session.execute(stmt)).all())

    # ---------- Órdenes (solo lectura) ----------

    async def get_order(self, order_id: UUID):
        from app.modules.orders.infra.models import OrderModel

        return await self._session.get(OrderModel, order_id)

    async def pending_orders(self, *, created_from=None, created_to=None, q_user_ids: Optional[set[UUID]] = None,
                             page: int = 1, page_size: int = 25, limit_all: bool = False,
                             trigger: str = TRIGGER_PAYMENT) -> tuple[list, int]:
        """Órdenes pagadas, no canceladas, sin comprobante vigente y listas según el momento de emisión
        (`domain.intifact.ready_to_issue`). Las más recientes primero."""
        from sqlalchemy.orm import aliased

        from app.modules.orders.infra.models import OrderModel as O

        with_doc = select(D.order_id).where(D.order_id.is_not(None), D.status.not_in(NO_VIGENTES))
        f = [O.payment_status == "paid", O.status != "cancelled", O.id.not_in(with_doc), O.total_snapshot > 0]
        if trigger == TRIGGER_SERVICE:
            parent = aliased(O)
            done_parents = select(parent.id).where(parent.status == "done")
            f.append(or_(and_(O.parent_order_id.is_(None), O.status == "done"), O.parent_order_id.in_(done_parents)))
        if created_from is not None:
            f.append(O.created_at >= created_from)
        if created_to is not None:
            f.append(O.created_at < created_to)
        if q_user_ids is not None:
            if not q_user_ids:
                return [], 0
            f.append(O.user_id.in_(q_user_ids))
        total = (await self._session.execute(select(func.count()).select_from(O).where(*f))).scalar_one()
        stmt = select(O).where(*f).order_by(O.created_at.desc())
        if not limit_all:
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        return await self._all(stmt), int(total)

    async def orders_by_id(self, ids: Iterable[UUID]) -> dict:
        from app.modules.orders.infra.models import OrderModel

        ids = [i for i in set(ids) if i]
        if not ids:
            return {}
        return {o.id: o for o in await self._all(select(OrderModel).where(OrderModel.id.in_(ids)))}

    async def order_pet_names(self, order_ids: Iterable[UUID]) -> dict[UUID, str]:
        """Nombre de la(s) mascota(s) de cada orden, por la tabla puente order_pets."""
        from app.modules.orders.infra.models import OrderPetModel
        from app.modules.pets.infra.models import PetModel

        ids = [i for i in set(order_ids) if i]
        if not ids:
            return {}
        rows = (await self._session.execute(
            select(OrderPetModel.order_id, PetModel.name).join(PetModel, PetModel.id == OrderPetModel.pet_id)
            .where(OrderPetModel.order_id.in_(ids)))).all()
        out: dict[UUID, list[str]] = {}
        for order_id, name in rows:
            out.setdefault(order_id, []).append(name)
        return {k: ", ".join(sorted(set(v))) for k, v in out.items()}

    # ---------- Usuarios (solo lectura) ----------

    async def users_by_id(self, ids: Iterable[UUID]) -> dict:
        from app.modules.iam.infra.models import UserModel

        ids = [i for i in set(ids) if i]
        if not ids:
            return {}
        return {u.id: u for u in await self._all(select(UserModel).where(UserModel.id.in_(ids)))}

    async def search_users(self, q: str, limit: int = 50, *, with_document: bool = False) -> list:
        from app.modules.iam.infra.models import UserModel as U

        pattern = f"%{q.strip()}%"
        stmt = select(U).where(U.role == "user", or_(
            (U.first_name + " " + U.last_name).ilike(pattern), U.dni.ilike(pattern), U.email.ilike(pattern)))
        if with_document:
            stmt = stmt.where(U.dni.is_not(None), func.length(func.trim(U.dni)) > 0)
        return await self._all(stmt.order_by(U.first_name, U.last_name).limit(limit))

    async def users_with_document(self, q: Optional[str]) -> list:
        from app.modules.iam.infra.models import UserModel as U

        stmt = select(U).where(U.role == "user", U.dni.is_not(None), func.length(func.trim(U.dni)) > 0)
        if q and q.strip():
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(or_((U.first_name + " " + U.last_name).ilike(pattern), U.dni.ilike(pattern),
                                  U.email.ilike(pattern)))
        return await self._all(stmt)

    async def customers_dni(self) -> tuple[int, int]:
        """(clientes activos, de ellos con DNI registrado)."""
        from app.modules.iam.infra.models import UserModel

        base = select(func.count()).select_from(UserModel).where(UserModel.role == "user", UserModel.is_active)
        total = (await self._session.execute(base)).scalar_one()
        with_dni = (await self._session.execute(
            base.where(UserModel.dni.is_not(None), func.length(func.trim(UserModel.dni)) > 0))).scalar_one()
        return total, with_dni

    # ---------- Empresas ----------

    async def get_company(self, company_id: UUID) -> Optional[InvoicingCompanyModel]:
        return await self._session.get(InvoicingCompanyModel, company_id)

    async def company_by_ruc(self, ruc: str) -> Optional[InvoicingCompanyModel]:
        C = InvoicingCompanyModel
        return (await self._session.execute(select(C).where(C.ruc == ruc))).scalars().first()

    async def companies(self, q: Optional[str]) -> list[InvoicingCompanyModel]:
        C = InvoicingCompanyModel
        stmt = select(C)
        if q and q.strip():
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(or_(C.legal_name.ilike(pattern), C.trade_name.ilike(pattern), C.ruc.ilike(pattern)))
        return await self._all(stmt.order_by(C.legal_name))
