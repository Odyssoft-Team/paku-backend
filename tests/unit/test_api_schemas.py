"""Esquemas de respuesta de la API.

Regresión 2026-10-05 (reportado por el front): en HoldOut, `date: Optional[date] = None` hacía que el
nombre del campo tapara al tipo y Pydantic lo tomara como None → POST/GET /holds respondían 500.
"""
import importlib
from datetime import date, datetime, timezone
from pathlib import Path
from types import NoneType
from uuid import uuid4

from pydantic import BaseModel

import app.modules
from app.modules.booking.api.schemas import HoldOut


def test_holdout_accepts_a_date():
    now = datetime.now(timezone.utc)
    out = HoldOut(id=uuid4(), user_id=uuid4(), pet_id=uuid4(), service_id=uuid4(), status="held",
                  expires_at=now, created_at=now, date=date(2026, 10, 10))
    assert out.date == date(2026, 10, 10)
    assert out.model_dump(mode="json")["date"] == "2026-10-10"


def _api_schema_models():
    # Se buscan los archivos directamente: la mayoría de los módulos no tienen __init__.py y
    # pkgutil.walk_packages no entra en ellos.
    modules_dir = Path(app.modules.__path__[0])
    for path in sorted(modules_dir.glob("*/api/schemas.py")):
        module = importlib.import_module(f"app.modules.{path.parent.parent.name}.api.schemas")
        for obj in vars(module).values():
            if isinstance(obj, type) and issubclass(obj, BaseModel) and obj.__module__ == module.__name__:
                yield obj


def test_no_api_field_is_accidentally_typed_as_none():
    """Ningún campo de la API puede quedar con tipo NoneType (síntoma del nombre que tapa al tipo)."""
    models = list(_api_schema_models())
    assert HoldOut in models and len(models) > 50  # el test recorre de verdad los esquemas
    broken = [
        f"{model.__module__}.{model.__name__}.{name}"
        for model in models
        for name, field in model.model_fields.items()
        if field.annotation is NoneType
    ]
    assert broken == []
