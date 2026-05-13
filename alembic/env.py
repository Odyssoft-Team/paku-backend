from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def _get_settings():
    load_dotenv()
    from app.core.settings import settings

    return settings


def _get_metadata():
    load_dotenv()
    from app.core.base import Base
    from app.modules.iam.infra.models import UserModel, UserAddressModel  # noqa: F401
    from app.modules.pets.infra.models import PetModel, PetWeightEntryModel  # noqa: F401
    from app.modules.booking.infra.models import HoldModel, AvailabilitySlotModel  # noqa: F401
    from app.modules.orders.infra.models import OrderModel, OrderAssignmentModel  # noqa: F401
    from app.modules.notifications.infra.models import NotificationModel  # noqa: F401
    from app.modules.push.infra.models import DeviceTokenModel  # noqa: F401
    from app.modules.cart.infra.models import CartSessionModel, CartItemModel  # noqa: F401
    from app.modules.catalog.infra.models import BreedModel  # noqa: F401
    from app.modules.store.infra.db_models import (
        CategoryModel,
        ProductModel,
        AddonModel,
        StorePriceRuleModel,
    )  # noqa: F401
    from app.modules.pet_records.infra.models import PetRecordModel  # noqa: F401
    from app.modules.iam.infra.models import UserSocialIdentityModel  # noqa: F401

    return Base.metadata


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = _get_metadata()


def get_url() -> str:
    settings = _get_settings()
    if not settings.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is required for migrations. Refusing to fall back to sqlite."
        )
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def include_object(obj, name, type_, reflected, compare_to):
    # Aquí pones los nombres de las tablas externas que quieres ignorar
    # O un prefijo, por ejemplo: if name.startswith("legacy_"): return False
    ignored_tables = ["tabla_externa_1", "tabla_externa_2", "otra_db_tabla"]

    if type_ == "table" and name in ignored_tables:
        return False
    return True


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = create_async_engine(
        get_url(),  # directo, sin pasar por config
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run() -> None:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        asyncio.run(run_migrations_online())


run()
