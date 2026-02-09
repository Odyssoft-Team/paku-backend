"""Hardcoded districts catalog for Paku.

This file contains the initial set of districts supported by the platform.
For now, we're starting with a subset of Lima districts where we have coverage.

In the future, this can be moved to a database or external API,
but for MVP it's simpler to have it hardcoded.
"""

from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    """Helper to get current UTC timestamp."""
    return datetime.now(timezone.utc)


# [BUSINESS]
# Lista de distritos activos donde Paku presta servicios.
# Cobertura completa de Lima Metropolitana (43 distritos).
# 
# Estructura:
# - id: código UBIGEO del INEI (identificador oficial del distrito)
# - name: nombre del distrito
# - province_name: provincia (Lima)
# - department_name: departamento (Lima)
# - active: si está disponible para servicios
DISTRICTS_DATA: list[dict[str, Any]] = [
    {"id": "150101", "name": "Lima", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150102", "name": "Ancón", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150103", "name": "Ate", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150104", "name": "Barranco", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150105", "name": "Breña", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150106", "name": "Carabayllo", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150107", "name": "Chaclacayo", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150108", "name": "Chorrillos", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150109", "name": "Cieneguilla", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150110", "name": "Comas", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150111", "name": "El Agustino", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150112", "name": "Independencia", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150113", "name": "Jesús María", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150114", "name": "La Molina", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150115", "name": "La Victoria", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150116", "name": "Lince", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150117", "name": "Los Olivos", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150118", "name": "Lurigancho", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150119", "name": "Lurín", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150120", "name": "Magdalena del Mar", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150121", "name": "Pueblo Libre", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150122", "name": "Miraflores", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150123", "name": "Pachacámac", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150124", "name": "Pucusana", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150125", "name": "Puente Piedra", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150126", "name": "Punta Hermosa", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150127", "name": "Punta Negra", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150128", "name": "Rímac", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150129", "name": "San Bartolo", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150130", "name": "San Borja", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150131", "name": "San Isidro", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150132", "name": "San Juan de Lurigancho", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150133", "name": "San Juan de Miraflores", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150134", "name": "San Luis", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150135", "name": "San Martín de Porres", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150136", "name": "San Miguel", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150137", "name": "Santa Anita", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150138", "name": "Santa María del Mar", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150139", "name": "Santa Rosa", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150140", "name": "Santiago de Surco", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150141", "name": "Surquillo", "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150142", "name": "Villa El Salvador", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150143", "name": "Villa María del Triunfo", "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
]


def get_all_districts(active_only: bool = True) -> list[dict[str, Any]]:
    """Get all districts from hardcoded data.
    
    Args:
        active_only: If True, return only active districts.
    
    Returns:
        List of district dictionaries.
    """
    if active_only:
        return [d for d in DISTRICTS_DATA if d.get("active", False)]
    return DISTRICTS_DATA.copy()


def get_district_by_id(district_id: str) -> dict[str, Any] | None:
    """Get a single district by ID.
    
    Args:
        district_id: The district UBIGEO code.
    
    Returns:
        District dictionary or None if not found.
    """
    for district in DISTRICTS_DATA:
        if district["id"] == district_id:
            return district.copy()
    return None
