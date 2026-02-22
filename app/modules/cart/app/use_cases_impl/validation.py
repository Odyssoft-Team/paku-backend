from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from fastapi import HTTPException, status

from app.modules.cart.domain.cart import CartItemKind

from .common import _kind_value, _meta_dict


def _validate_date_format(date_str: str, field_name: str) -> None:
    """Valida que la fecha tenga formato YYYY-MM-DD"""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format. Expected YYYY-MM-DD, got '{date_str}'",
        )
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format. Expected YYYY-MM-DD, got '{date_str}'",
        )


def _validate_time_format(time_str: str, field_name: str) -> None:
    """Valida que la hora tenga formato HH:MM"""
    if not re.fullmatch(r"\d{2}:\d{2}", time_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format. Expected HH:MM, got '{time_str}'",
        )
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format. Expected HH:MM, got '{time_str}'",
        )


def _validate_single_base_service(items: list[dict[str, Any]]) -> None:
    """Valida que solo haya un servicio base en la lista de items."""
    base_count = sum(1 for item in items if _kind_value(item.get("kind")) == CartItemKind.service_base.value)
    if base_count > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot have multiple base services in cart. Only 1 base service + addons allowed.",
        )
    if base_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cart must have at least one base service",
        )


def _validate_required_meta_fields(items: list[dict[str, Any]]) -> None:
    """Valida que los servicios base tengan los campos requeridos en meta."""
    for item in items:
        if _kind_value(item.get("kind")) == CartItemKind.service_base.value:
            meta = _meta_dict(item.get("meta"))

            if not meta.get("pet_id"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Service '{item.get('name', 'unknown')}' requires 'pet_id' in meta",
                )

            scheduled_date = meta.get("scheduled_date")
            if not scheduled_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Service '{item.get('name', 'unknown')}' requires 'scheduled_date' in meta (format: YYYY-MM-DD)"
                    ),
                )
            _validate_date_format(str(scheduled_date), "scheduled_date")

            scheduled_time = meta.get("scheduled_time")
            if not scheduled_time:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Service '{item.get('name', 'unknown')}' requires 'scheduled_time' in meta (format: HH:MM)"
                    ),
                )
            _validate_time_format(str(scheduled_time), "scheduled_time")


def _validate_addon_dependencies(items: list[dict[str, Any]]) -> None:
    """Valida que los addons referencien correctamente al servicio base."""
    base_service = next(
        (item for item in items if _kind_value(item.get("kind")) == CartItemKind.service_base.value),
        None,
    )

    if not base_service:
        return

    base_ref_id = str(base_service.get("ref_id"))

    for item in items:
        if _kind_value(item.get("kind")) == CartItemKind.service_addon.value:
            meta = _meta_dict(item.get("meta"))
            requires_base = meta.get("requires_base")

            if requires_base and str(requires_base) != base_ref_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Addon '{item.get('name', 'unknown')}' requires base service '{requires_base}', "
                        f"but cart has '{base_ref_id}'"
                    ),
                )
