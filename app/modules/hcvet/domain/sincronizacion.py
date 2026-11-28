"""Estados, reintentos y datos del propietario para la sincronización con HCVet (feature 0028, REQUIREMENTS §7 y §11).

Cada envío a HCVet es una **operación** guardada en ``hcvet_operaciones`` (outbox transaccional) en la misma
transacción que la decisión del cliente; un job del scheduler la envía después. Si HCVet no está, la operación espera
y Paku sigue funcionando.

Estados de una operación:

- ``pendiente``: por enviar (o esperando a que el propietario quede vinculado).
- ``bloqueado``: falta una condición que no se resuelve reintentando (datos del perfil). Se revisa cada
  ``REVISION_BLOQUEADAS_MINUTOS``.
- ``sincronizando``: enviada, sin respuesta todavía. Si queda colgada más de ``COLGADA_MINUTOS`` se reintenta con la
  misma clave de idempotencia.
- ``sincronizado``: HCVet la aceptó.
- ``fallido``: rechazo permanente (401, 403, 404, 422) o reintentos agotados. Con ``reintentable`` se reintenta sola.
- ``conflicto``: HCVet respondió 409 (dato verificado o más reciente, DNI de otro propietario…). No se reintenta.
- ``cancelado``: el cliente revocó la integración antes de enviarla.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

PENDIENTE = "pendiente"
BLOQUEADO = "bloqueado"
SINCRONIZANDO = "sincronizando"
SINCRONIZADO = "sincronizado"
FALLIDO = "fallido"
CONFLICTO = "conflicto"
CANCELADO = "cancelado"
ESTADOS_OPERACION = (PENDIENTE, BLOQUEADO, SINCRONIZANDO, SINCRONIZADO, FALLIDO, CONFLICTO, CANCELADO)
ABIERTOS = (PENDIENTE, BLOQUEADO, SINCRONIZANDO, FALLIDO)

# Estado del vínculo del cliente con HCVet (lo que ve el front). "vinculado" solo cuando HCVet lo confirmó.
VINCULO_PENDIENTE = "pendiente"
VINCULO_BLOQUEADO = "bloqueado"
VINCULO_SINCRONIZANDO = "sincronizando"
VINCULADO = "vinculado"
VINCULO_FALLIDO = "fallido"
VINCULO_CONFLICTO = "conflicto"
VINCULO_REVOCADO = "revocado"

# Tipos de operación (entidad: propietario).
ALTA = "alta_propietario"  # POST /propietarios; si el DNI ya existe, vinculación con evidencia
CONSENTIMIENTO = "registrar_consentimiento"  # PUT /propietarios/{dni}/consentimientos/{tipo}
ACTUALIZACION = "actualizar_propietario"  # PATCH /propietarios/{dni}
REVOCACION = "revocar_autorizacion"  # DELETE /propietarios/{dni}/autorizaciones/{id}
# GET /propietarios/{dni}/autorizaciones: con un vínculo básico, detecta si el dueño amplió el acceso desde HCVet.
REVISION_ACCESO = "revisar_acceso"
TIPOS_OPERACION = (ALTA, CONSENTIMIENTO, ACTUALIZACION, REVOCACION, REVISION_ACCESO)
# No son cambios del cliente pendientes de enviar: no cuentan en ``operaciones_pendientes``.
TIPOS_DE_MANTENIMIENTO = (REVISION_ACCESO,)

# Acceso del vínculo (HCVet D-105). Completo: Paku dio de alta al propietario, o el dueño lo otorgó con su sesión.
# Básico: Paku se vinculó a un propietario que ya existía; evita duplicados, pero no abre sus datos, mascotas,
# historiales ni consentimientos previos.
ACCESO_COMPLETO = "completo"
ACCESO_BASICO = "basico"
REVISION_ACCESO_HORAS = 6

# Motivos (códigos estables para el front y el admin; sin datos personales).
DATOS_INCOMPLETOS = "DATOS_INCOMPLETOS"
ESPERA_VINCULO = "ESPERA_VINCULO"
INTEGRACION_INACTIVA = "INTEGRACION_INACTIVA"
HCVET_NO_DISPONIBLE = "HCVET_NO_DISPONIBLE"
REINTENTOS_AGOTADOS = "REINTENTOS_AGOTADOS"
RECHAZADO = "RECHAZADO"
CONFLICTO_HCVET = "CONFLICTO_HCVET"
AUTORIZACION_NO_VIGENTE = "AUTORIZACION_NO_VIGENTE"
INTEGRACION_REVOCADA = "INTEGRACION_REVOCADA"
ACCESO_BASICO_MOTIVO = "ACCESO_BASICO"

MAX_INTENTOS = 8
ESPERAS_MINUTOS = (1, 5, 15, 30, 60, 120, 240)
COLGADA_MINUTOS = 10
REVISION_BLOQUEADAS_MINUTOS = 60


def proximo_intento(intentos: int, *, ahora: datetime, retry_after: Optional[int] = None) -> Optional[datetime]:
    """Cuándo reintentar tras ``intentos`` fallas temporales; None si ya no quedan. Respeta ``Retry-After``."""
    if intentos >= MAX_INTENTOS:
        return None
    espera = timedelta(minutes=ESPERAS_MINUTOS[min(max(intentos, 1), len(ESPERAS_MINUTOS)) - 1])
    if retry_after:
        espera = max(espera, timedelta(seconds=retry_after))
    return ahora + espera


_DIGITOS_LARGOS = re.compile(r"\d{6,}")
_CORREO = re.compile(r"[^\s@]+@[^\s@]+")


def sin_datos_personales(texto: str, limite: int = 300) -> str:
    """Para guardar errores de HCVet: oculta DNI, teléfonos y correos que pudieran venir en el detalle."""
    return _CORREO.sub("[correo]", _DIGITOS_LARGOS.sub("[número]", texto or ""))[:limite]


# --- Datos del propietario que Paku envía (REQUIREMENTS §7.2) ---

_TELEFONO = re.compile(r"^\+?[0-9]{6,15}$")
_DNI = re.compile(r"^[0-9]{8}$")


def normalizar_telefono(telefono: Optional[str]) -> Optional[str]:
    if not telefono:
        return None
    limpio = re.sub(r"[\s\-().]", "", telefono)
    return limpio if _TELEFONO.match(limpio) else None


@dataclass(frozen=True)
class DatosPropietario:
    """Lo que HCVet recibe del cliente. Nombres y apellidos son los **legales** (de la consulta del DNI), no el nombre
    visible de Paku, que es libre y puede ser un apodo."""

    dni: str
    nombres: str
    apellidos: str
    distrito: str
    telefono: str
    email: str


def datos_para_hcvet(usuario: Any, distrito: Optional[str]) -> tuple[Optional[DatosPropietario], list[str]]:
    """Datos del alta o la lista de lo que falta (nombres de campo, sin valores)."""
    faltan: list[str] = []
    dni = (usuario.dni or "").strip()
    if not _DNI.match(dni):
        faltan.append("dni")
    if not (usuario.legal_first_name and usuario.legal_last_name):
        faltan.append("nombres_legales")
    telefono = normalizar_telefono(usuario.phone)
    if telefono is None:
        faltan.append("telefono")
    if not distrito:
        faltan.append("distrito")
    if not usuario.email:
        faltan.append("email")
    if faltan:
        return None, faltan
    return (
        DatosPropietario(
            dni=dni,
            nombres=usuario.legal_first_name.strip()[:100],
            apellidos=usuario.legal_last_name.strip()[:100],
            distrito=distrito.strip()[:100],
            telefono=telefono,
            email=usuario.email,
        ),
        [],
    )


# Política de actualización (REQUIREMENTS §7.2, HCVet D-093/D-095):
# - Solo se notifican a HCVet el teléfono y los nombres legales; el distrito y el correo se envían en el alta.
#   El nombre visible de Paku nunca se envía.
# - Cada PATCH lleva ``datos_al`` (cuándo cambió el dato en Paku): HCVet rechaza con 409 si tiene un dato más reciente
#   o verificado, y Paku deja la operación en ``conflicto`` sin reintentar ni sobrescribir.
# - Los nombres legales van con su verificación por campo (consulta a Datos Perú, D-095), que no es titularidad.
CAMPOS_NOTIFICABLES = ("telefono", "nombres", "apellidos")
METODO_VERIFICACION_NOMBRES = "consulta_datos_peru"
