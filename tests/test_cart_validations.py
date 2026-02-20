"""
Tests para validaciones del carrito.

Verifica que las validaciones de negocio funcionen correctamente:
- Solo 1 servicio base por carrito
- Meta requeridos (pet_id, scheduled_date, scheduled_time)
- Formato de fecha/hora
- Dependencias de addons
- Validación completa pre-checkout
"""
import pytest
from uuid import uuid4
from fastapi import HTTPException

from app.modules.cart.app.use_cases import (
    _validate_single_base_service,
    _validate_required_meta_fields,
    _validate_addon_dependencies,
    _validate_date_format,
    _validate_time_format,
)


class TestSingleBaseServiceValidation:
    """Tests para validación de servicio base único"""
    
    def test_valid_single_base_service(self):
        """Debe aceptar 1 servicio base + addons"""
        items = [
            {"kind": "service_base", "ref_id": "base-1", "name": "Clásico"},
            {"kind": "service_addon", "ref_id": "addon-1", "name": "Corte uñas"},
        ]
        # No debe lanzar excepción
        _validate_single_base_service(items)
    
    def test_reject_multiple_base_services(self):
        """Debe rechazar múltiples servicios base"""
        items = [
            {"kind": "service_base", "ref_id": "base-1", "name": "Clásico"},
            {"kind": "service_base", "ref_id": "base-2", "name": "Premium"},
        ]
        with pytest.raises(HTTPException) as exc_info:
            _validate_single_base_service(items)
        
        assert exc_info.value.status_code == 400
        assert "multiple base services" in exc_info.value.detail.lower()
    
    def test_reject_no_base_service(self):
        """Debe rechazar carrito sin servicio base"""
        items = [
            {"kind": "service_addon", "ref_id": "addon-1", "name": "Corte uñas"},
        ]
        with pytest.raises(HTTPException) as exc_info:
            _validate_single_base_service(items)
        
        assert exc_info.value.status_code == 400
        assert "at least one base service" in exc_info.value.detail.lower()
    
    def test_accept_only_base_service(self):
        """Debe aceptar solo servicio base sin addons"""
        items = [
            {"kind": "service_base", "ref_id": "base-1", "name": "Clásico"},
        ]
        # No debe lanzar excepción
        _validate_single_base_service(items)


class TestRequiredMetaFieldsValidation:
    """Tests para validación de campos requeridos en meta"""
    
    def test_valid_meta_fields(self):
        """Debe aceptar meta completo"""
        items = [
            {
                "kind": "service_base",
                "ref_id": "base-1",
                "name": "Clásico",
                "meta": {
                    "pet_id": str(uuid4()),
                    "scheduled_date": "2026-02-25",
                    "scheduled_time": "10:00"
                }
            }
        ]
        # No debe lanzar excepción
        _validate_required_meta_fields(items)
    
    def test_reject_missing_pet_id(self):
        """Debe rechazar meta sin pet_id"""
        items = [
            {
                "kind": "service_base",
                "ref_id": "base-1",
                "name": "Clásico",
                "meta": {
                    "scheduled_date": "2026-02-25",
                    "scheduled_time": "10:00"
                }
            }
        ]
        with pytest.raises(HTTPException) as exc_info:
            _validate_required_meta_fields(items)
        
        assert exc_info.value.status_code == 400
        assert "pet_id" in exc_info.value.detail.lower()
    
    def test_reject_missing_scheduled_date(self):
        """Debe rechazar meta sin scheduled_date"""
        items = [
            {
                "kind": "service_base",
                "ref_id": "base-1",
                "name": "Clásico",
                "meta": {
                    "pet_id": str(uuid4()),
                    "scheduled_time": "10:00"
                }
            }
        ]
        with pytest.raises(HTTPException) as exc_info:
            _validate_required_meta_fields(items)
        
        assert exc_info.value.status_code == 400
        assert "scheduled_date" in exc_info.value.detail.lower()
    
    def test_reject_missing_scheduled_time(self):
        """Debe rechazar meta sin scheduled_time"""
        items = [
            {
                "kind": "service_base",
                "ref_id": "base-1",
                "name": "Clásico",
                "meta": {
                    "pet_id": str(uuid4()),
                    "scheduled_date": "2026-02-25"
                }
            }
        ]
        with pytest.raises(HTTPException) as exc_info:
            _validate_required_meta_fields(items)
        
        assert exc_info.value.status_code == 400
        assert "scheduled_time" in exc_info.value.detail.lower()
    
    def test_reject_invalid_date_format(self):
        """Debe rechazar formato de fecha inválido"""
        items = [
            {
                "kind": "service_base",
                "ref_id": "base-1",
                "name": "Clásico",
                "meta": {
                    "pet_id": str(uuid4()),
                    "scheduled_date": "25-02-2026",  # formato inválido
                    "scheduled_time": "10:00"
                }
            }
        ]
        with pytest.raises(HTTPException) as exc_info:
            _validate_required_meta_fields(items)
        
        assert exc_info.value.status_code == 400
        assert "YYYY-MM-DD" in exc_info.value.detail
    
    def test_reject_invalid_time_format(self):
        """Debe rechazar formato de hora inválido"""
        items = [
            {
                "kind": "service_base",
                "ref_id": "base-1",
                "name": "Clásico",
                "meta": {
                    "pet_id": str(uuid4()),
                    "scheduled_date": "2026-02-25",
                    "scheduled_time": "10:00:00"  # formato inválido
                }
            }
        ]
        with pytest.raises(HTTPException) as exc_info:
            _validate_required_meta_fields(items)
        
        assert exc_info.value.status_code == 400
        assert "HH:MM" in exc_info.value.detail
    
    def test_addons_dont_require_meta(self):
        """Addons no requieren meta completo"""
        items = [
            {
                "kind": "service_base",
                "ref_id": "base-1",
                "name": "Clásico",
                "meta": {
                    "pet_id": str(uuid4()),
                    "scheduled_date": "2026-02-25",
                    "scheduled_time": "10:00"
                }
            },
            {
                "kind": "service_addon",
                "ref_id": "addon-1",
                "name": "Corte uñas",
                "meta": {}  # Meta vacío OK para addons
            }
        ]
        # No debe lanzar excepción
        _validate_required_meta_fields(items)


class TestAddonDependenciesValidation:
    """Tests para validación de dependencias de addons"""
    
    def test_valid_addon_dependency(self):
        """Debe aceptar addon que referencia al servicio base correcto"""
        base_ref = "base-uuid-123"
        items = [
            {"kind": "service_base", "ref_id": base_ref, "name": "Clásico"},
            {
                "kind": "service_addon",
                "ref_id": "addon-1",
                "name": "Corte uñas",
                "meta": {"requires_base": base_ref}
            }
        ]
        # No debe lanzar excepción
        _validate_addon_dependencies(items)
    
    def test_addon_without_requires_base(self):
        """Debe aceptar addon sin requires_base (se asume servicio base del carrito)"""
        items = [
            {"kind": "service_base", "ref_id": "base-1", "name": "Clásico"},
            {
                "kind": "service_addon",
                "ref_id": "addon-1",
                "name": "Corte uñas",
                "meta": {}  # Sin requires_base
            }
        ]
        # No debe lanzar excepción
        _validate_addon_dependencies(items)
    
    def test_reject_mismatched_addon_dependency(self):
        """Debe rechazar addon que referencia a servicio base incorrecto"""
        items = [
            {"kind": "service_base", "ref_id": "classic-uuid", "name": "Clásico"},
            {
                "kind": "service_addon",
                "ref_id": "addon-1",
                "name": "Corte uñas",
                "meta": {"requires_base": "premium-uuid"}  # No coincide
            }
        ]
        with pytest.raises(HTTPException) as exc_info:
            _validate_addon_dependencies(items)
        
        assert exc_info.value.status_code == 400
        assert "requires base service" in exc_info.value.detail.lower()


class TestDateTimeFormatValidation:
    """Tests para validación de formato de fecha y hora"""
    
    def test_valid_date_format(self):
        """Debe aceptar formato YYYY-MM-DD"""
        _validate_date_format("2026-02-25", "scheduled_date")
        _validate_date_format("2026-12-31", "scheduled_date")
        _validate_date_format("2026-01-01", "scheduled_date")
    
    def test_reject_invalid_date_formats(self):
        """Debe rechazar formatos de fecha inválidos"""
        invalid_dates = [
            "25-02-2026",      # DD-MM-YYYY
            "02/25/2026",      # MM/DD/YYYY
            "2026/02/25",      # YYYY/MM/DD
            "25.02.2026",      # DD.MM.YYYY
            "2026-2-25",       # Sin ceros
            "2026-13-01",      # Mes inválido
            "2026-02-32",      # Día inválido
            "not-a-date",      # Texto
        ]
        
        for invalid_date in invalid_dates:
            with pytest.raises(HTTPException) as exc_info:
                _validate_date_format(invalid_date, "scheduled_date")
            
            assert exc_info.value.status_code == 400
            assert "YYYY-MM-DD" in exc_info.value.detail
    
    def test_valid_time_format(self):
        """Debe aceptar formato HH:MM"""
        _validate_time_format("10:00", "scheduled_time")
        _validate_time_format("23:59", "scheduled_time")
        _validate_time_format("00:00", "scheduled_time")
    
    def test_reject_invalid_time_formats(self):
        """Debe rechazar formatos de hora inválidos"""
        invalid_times = [
            "10:00:00",        # HH:MM:SS
            "10",              # Solo hora
            "10:0",            # Sin cero
            "24:00",           # Hora inválida
            "10:60",           # Minuto inválido
            "not-a-time",      # Texto
        ]
        
        for invalid_time in invalid_times:
            with pytest.raises(HTTPException) as exc_info:
                _validate_time_format(invalid_time, "scheduled_time")
            
            assert exc_info.value.status_code == 400
            assert "HH:MM" in exc_info.value.detail


class TestCompleteCartValidation:
    """Tests para validación completa de carrito (use case ValidateCart)"""
    
    # Nota: Estos tests requieren mock del repositorio
    # Se implementan en test_cart_flow.py con fixtures de BD
    pass


# Ejecutar tests:
# pytest tests/test_cart_validations.py -v
