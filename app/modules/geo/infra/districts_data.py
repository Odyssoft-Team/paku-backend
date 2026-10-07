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
# - lat/lng: centro aproximado del distrito; centra la búsqueda de direcciones
#   (feature 0002). No se exponen en GET /geo/districts.
DISTRICTS_DATA: list[dict[str, Any]] = [
    {"id": "150101", "name": "Lima", "lat": -12.0464, "lng": -77.0428, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150102", "name": "Ancón", "lat": -11.7372, "lng": -77.1761, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150103", "name": "Ate", "lat": -12.0464, "lng": -76.9047, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150104", "name": "Barranco", "lat": -12.1467, "lng": -77.0205, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150105", "name": "Breña", "lat": -12.0594, "lng": -77.0497, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150106", "name": "Carabayllo", "lat": -11.8653, "lng": -77.0428, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150107", "name": "Chaclacayo", "lat": -11.9736, "lng": -76.765, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150108", "name": "Chorrillos", "lat": -12.1686, "lng": -77.0117, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150109", "name": "Cieneguilla", "lat": -12.0947, "lng": -76.8189, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150110", "name": "Comas", "lat": -11.9389, "lng": -77.0533, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150111", "name": "El Agustino", "lat": -12.0439, "lng": -77.0069, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150112", "name": "Independencia", "lat": -11.9933, "lng": -77.0531, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150113", "name": "Jesús María", "lat": -12.0725, "lng": -77.0436, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150114", "name": "La Molina", "lat": -12.0797, "lng": -76.9403, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150115", "name": "La Victoria", "lat": -12.0686, "lng": -77.0197, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150116", "name": "Lince", "lat": -12.0844, "lng": -77.0339, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150117", "name": "Los Olivos", "lat": -11.9617, "lng": -77.0719, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150118", "name": "Lurigancho", "lat": -11.9719, "lng": -76.7442, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150119", "name": "Lurín", "lat": -12.2744, "lng": -76.8728, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150120", "name": "Magdalena del Mar", "lat": -12.0917, "lng": -77.0736, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150121", "name": "Pueblo Libre", "lat": -12.0764, "lng": -77.0631, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150122", "name": "Miraflores", "lat": -12.1197, "lng": -77.0283, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150123", "name": "Pachacámac", "lat": -12.2492, "lng": -76.8644, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150124", "name": "Pucusana", "lat": -12.4781, "lng": -76.7994, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150125", "name": "Puente Piedra", "lat": -11.8586, "lng": -77.0731, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150126", "name": "Punta Hermosa", "lat": -12.3347, "lng": -76.8228, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150127", "name": "Punta Negra", "lat": -12.3614, "lng": -76.7989, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150128", "name": "Rímac", "lat": -12.0367, "lng": -77.0414, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150129", "name": "San Bartolo", "lat": -12.3911, "lng": -76.7772, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150130", "name": "San Borja", "lat": -12.092, "lng": -77.0053, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150131", "name": "San Isidro", "lat": -12.0968, "lng": -77.0353, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150132", "name": "San Juan de Lurigancho", "lat": -11.9842, "lng": -77.0131, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150133", "name": "San Juan de Miraflores", "lat": -12.1569, "lng": -76.9739, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150134", "name": "San Luis", "lat": -12.0744, "lng": -76.9969, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150135", "name": "San Martín de Porres", "lat": -12.0131, "lng": -77.0794, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150136", "name": "San Miguel", "lat": -12.0775, "lng": -77.0861, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150137", "name": "Santa Anita", "lat": -12.045, "lng": -76.9689, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150138", "name": "Santa María del Mar", "lat": -12.405, "lng": -76.765, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150139", "name": "Santa Rosa", "lat": -11.795, "lng": -77.1644, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150140", "name": "Santiago de Surco", "lat": -12.1469, "lng": -76.9947, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150141", "name": "Surquillo", "lat": -12.1133, "lng": -77.0194, "province_name": "Lima", "department_name": "Lima", "active": True, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150142", "name": "Villa El Salvador", "lat": -12.2042, "lng": -76.9392, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
    {"id": "150143", "name": "Villa María del Triunfo", "lat": -12.1608, "lng": -76.9339, "province_name": "Lima", "department_name": "Lima", "active": False, "created_at": utcnow(), "updated_at": utcnow()},
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
