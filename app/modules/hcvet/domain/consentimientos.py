"""Consentimientos del cliente para la integración con HCVet (feature 0028, REQUIREMENTS §6).

Cinco decisiones distintas, ninguna marcada por defecto y ninguna equivalente a otra:

- ``integracion_hcvet``: autoriza a Paku a registrar o vincular al cliente como propietario en HCVet y a actuar en su
  nombre con los alcances de ``ALCANCES_PAKU`` (la autorización delegada de HCVet). Sin ella no se envía nada.
- ``indexacion_veterinaria``: compartir su información veterinaria (otras veterinarias pueden encontrarlo por DNI).
- ``historial_compartido``: que las plataformas autorizadas consulten su historia clínica.
- ``registro_eventos``: que las plataformas autorizadas registren eventos de sus mascotas.
- ``uso_comercial``: uso comercial de sus datos (en HCVet se registra sin efecto todavía).

Rechazar cualquiera no limita los servicios comerciales de Paku (reservas, órdenes, tienda).

Los textos son **provisionales** (``TEXTOS_APROBADOS = False``): deben revisarse y aprobarse antes de producción. Al
aprobarlos cambia la versión y las decisiones anteriores quedan registradas con la versión que vio el cliente.
"""

from __future__ import annotations

from dataclasses import dataclass

INTEGRACION = "integracion_hcvet"
INDEXACION = "indexacion_veterinaria"
HISTORIAL = "historial_compartido"
REGISTRO_EVENTOS = "registro_eventos"
USO_COMERCIAL = "uso_comercial"

TIPOS = (INTEGRACION, INDEXACION, HISTORIAL, REGISTRO_EVENTOS, USO_COMERCIAL)
# Los que tienen un consentimiento con el mismo nombre en HCVet (PUT /propietarios/{dni}/consentimientos/{tipo}).
TIPOS_HCVET = (INDEXACION, HISTORIAL, REGISTRO_EVENTOS, USO_COMERCIAL)
# Van en ``consentimientos`` del alta; indexación y uso comercial van como booleanos del propietario (HCVet).
TIPOS_INICIALES_HCVET = (HISTORIAL, REGISTRO_EVENTOS)
# HCVet exige indexación y uso comercial explícitos en el alta: sin esas decisiones no se puede registrar.
REQUERIDOS_PARA_ALTA = (INTEGRACION, INDEXACION, USO_COMERCIAL)

CANALES = ("web", "app")

TEXTOS_APROBADOS = False
VERSION_TEXTOS = "borrador-2026-11-28"

# Alcances que Paku pide a HCVet en la autorización delegada (catálogo de HCVet, D-088). Se eligen explícitamente:
# no incluye mascota.actualizar (la ficha la edita el dueño) ni evento.corregir (fase 3 de HCVet).
ALCANCES_PAKU = (
    "propietario.registrar",
    "propietario.consultar",
    "propietario.actualizar",
    "mascota.consultar",
    "mascota.registrar",
    "historial.consultar",
    "evento.registrar",
)


@dataclass(frozen=True)
class TextoConsentimiento:
    tipo: str
    titulo: str
    texto: str
    finalidad: str  # se envía a HCVet como ``finalidad`` (hasta 200 caracteres)


TEXTOS: dict[str, TextoConsentimiento] = {
    INTEGRACION: TextoConsentimiento(
        INTEGRACION,
        "Historial clínico en HCVet",
        "Autorizo a Paku a registrarme como propietario en HCVet, el historial clínico veterinario, con mi DNI, nombres "
        "y apellidos oficiales, distrito, teléfono y correo, y a consultar y registrar en mi nombre los datos de mis "
        "mascotas. Puedo revocarlo cuando quiera; lo ya registrado en HCVet se conserva.",
        "Registro y vinculación del propietario en HCVet por Paku",
    ),
    INDEXACION: TextoConsentimiento(
        INDEXACION,
        "Compartir con otras veterinarias",
        "Permito que otras veterinarias que usan HCVet me encuentren por mi DNI.",
        "Búsqueda del propietario por DNI en establecimientos veterinarios",
    ),
    HISTORIAL: TextoConsentimiento(
        HISTORIAL,
        "Consultar la historia clínica",
        "Permito que las plataformas que autoricé consulten la historia clínica de mis mascotas.",
        "Consulta de la historia clínica por plataformas autorizadas",
    ),
    REGISTRO_EVENTOS: TextoConsentimiento(
        REGISTRO_EVENTOS,
        "Registrar atenciones",
        "Permito que las plataformas que autoricé registren atenciones (baños, vacunas, consultas) de mis mascotas.",
        "Registro de eventos de las mascotas por plataformas autorizadas",
    ),
    USO_COMERCIAL: TextoConsentimiento(
        USO_COMERCIAL,
        "Uso comercial de mis datos",
        "Permito el uso comercial de mis datos. Es opcional y no cambia los servicios de Paku que puedo usar.",
        "Uso comercial de los datos del propietario",
    ),
}


class VersionDeTextoDesactualizada(Exception):
    """El cliente decidió sobre un texto que ya no es el vigente."""


class DecisionInvalida(Exception):
    pass


@dataclass(frozen=True)
class Decision:
    tipo: str
    concedido: bool
    version_texto: str


def validar_decisiones(decisiones: list[Decision]) -> None:
    """Tipos conocidos, sin repetir, y sobre el texto vigente (evidencia de lo que el cliente vio)."""
    if not decisiones:
        raise DecisionInvalida("Indica al menos una decisión.")
    tipos = [d.tipo for d in decisiones]
    if len(set(tipos)) != len(tipos):
        raise DecisionInvalida("Cada consentimiento se indica una sola vez.")
    for d in decisiones:
        if d.tipo not in TIPOS:
            raise DecisionInvalida(f"Consentimiento desconocido: {d.tipo}.")
        if d.version_texto != VERSION_TEXTOS:
            raise VersionDeTextoDesactualizada("El texto cambió. Vuelve a leerlo antes de decidir.")
