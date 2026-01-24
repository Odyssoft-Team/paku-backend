import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder

from app.modules.booking.domain.hold import Hold, HoldStatus
from app.modules.booking.infra.postgres_hold_repository import PostgresHoldRepository
from app.modules.commerce.infra.postgres_commerce_repository import PostgresCommerceRepository
from app.modules.pets.domain.pet import PetRepository


@dataclass
class CreateHold:
    repo: PostgresHoldRepository

    async def execute(self, *, user_id: UUID, pet_id: UUID, service_id: UUID) -> Hold:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        return await self.repo.create_hold(user_id=user_id, pet_id=pet_id, service_id=service_id, expires_at=expires_at)


@dataclass
class ConfirmHold:
    repo: PostgresHoldRepository
    commerce_repo: PostgresCommerceRepository
    pets_repo: PetRepository

    def _run_quote_sync(self, *, pet_id: UUID, base_service_id: UUID) -> Any:
        from app.modules.commerce.app.use_cases import Quote

        async def _run() -> Any:
            return await Quote(repo=self.commerce_repo, pets_repo=self.pets_repo).execute(
                pet_id=pet_id,
                base_service_id=base_service_id,
                addon_ids=[],
            )

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_run())

        result: dict[str, Any] = {}
        error: list[BaseException] = []

        def _worker() -> None:
            try:
                result["value"] = asyncio.run(_run())
            except BaseException as e:  # pragma: no cover
                error.append(e)

        import threading

        t = threading.Thread(target=_worker)
        t.start()
        t.join()
        if error:
            raise error[0]
        return result["value"]

    async def execute(self, *, hold_id: UUID) -> Hold:
        hold = await self.repo.get_hold(hold_id)
        if not hold:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hold not found")
        if hold.status == HoldStatus.expired:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hold cannot be confirmed")
        if hold.status != HoldStatus.held:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hold cannot be confirmed")
        quote = self._run_quote_sync(pet_id=hold.pet_id, base_service_id=hold.service_id)
        snapshot = jsonable_encoder(quote)
        updated = await self.repo.update_status(hold_id, HoldStatus.confirmed, quote_snapshot=snapshot)
        return updated or hold


@dataclass
class CancelHold:
    repo: PostgresHoldRepository

    async def execute(self, *, hold_id: UUID) -> Hold:
        hold = await self.repo.get_hold(hold_id)
        if not hold:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hold not found")
        if hold.status == HoldStatus.cancelled:
            return hold
        if hold.status != HoldStatus.held:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hold cannot be cancelled")
        updated = await self.repo.update_status(hold_id, HoldStatus.cancelled)
        return updated or hold
