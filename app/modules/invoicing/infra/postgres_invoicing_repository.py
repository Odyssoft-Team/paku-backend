from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.invoicing.infra.models import InvoicingProviderModel


class PostgresInvoicingRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def get(self, provider: str) -> Optional[InvoicingProviderModel]:
        return await self._session.get(InvoicingProviderModel, provider)

    async def save(self, model: InvoicingProviderModel) -> InvoicingProviderModel:
        self._session.add(model)
        await self._session.commit()
        return model

    async def customers_dni(self) -> tuple[int, int]:
        """(clientes activos, de ellos con DNI registrado). Para saber si se podría emitir boleta con DNI."""
        from app.modules.iam.infra.models import UserModel

        base = select(func.count()).select_from(UserModel).where(UserModel.role == "user", UserModel.is_active)
        total = (await self._session.execute(base)).scalar_one()
        with_dni = (await self._session.execute(
            base.where(UserModel.dni.is_not(None), func.length(func.trim(UserModel.dni)) > 0)
        )).scalar_one()
        return total, with_dni
