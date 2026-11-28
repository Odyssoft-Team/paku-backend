"""Diagnóstico de DNI inválidos o duplicados en ``users`` (feature 0027, PAKU-USERS-009).

Solo lectura: abre una transacción READ ONLY y no modifica, elimina ni fusiona usuarios. Sirve para preparar la
migración ``e8f3a1c7d5b2`` (índice único y formato de ``users.dni``), que se niega a aplicarse mientras existan datos
inválidos o duplicados.

Uso (con DATABASE_URL apuntando a la base que se quiere revisar):

    python -m scripts.diagnostico_dni            # informe legible
    python -m scripts.diagnostico_dni --json     # informe en JSON

El informe no muestra DNI completos: solo los 4 últimos dígitos. Las correcciones las decide una persona: el informe
sugiere qué hacer, pero no lo hace.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Iterable, Optional

_PATRON = re.compile(r"^[0-9]{8}$")
_SEPARADORES = re.compile(r"[\s.\-]")

SUGERENCIA_DUPLICADO = (
    "Revisar manualmente qué cuenta es del titular (contactar a los usuarios). No fusionar ni eliminar "
    "automáticamente: dejar el DNI solo en una cuenta y pedir a las demás que lo corrijan."
)


@dataclass(frozen=True)
class FilaUsuario:
    id: str
    role: str
    dni: str
    created_at: str


@dataclass
class Hallazgo:
    id: str
    role: str
    dni_enmascarado: str
    categoria: str  # vacio | normalizable | invalido
    sugerencia: str


@dataclass
class GrupoDuplicado:
    dni_enmascarado: str
    usuarios: list[dict]


@dataclass
class Informe:
    total_con_dni: int = 0
    validos: int = 0
    hallazgos: list[Hallazgo] = field(default_factory=list)
    duplicados: list[GrupoDuplicado] = field(default_factory=list)

    @property
    def listo_para_migrar(self) -> bool:
        return not self.hallazgos and not self.duplicados


def enmascarar(dni: str) -> str:
    limpio = dni.strip()
    if len(limpio) <= 4:
        return "*" * len(limpio)
    return "*" * (len(limpio) - 4) + limpio[-4:]


def normalizar(dni: str) -> Optional[str]:
    """El DNI de 8 dígitos que representa el valor, si quitando espacios, puntos o guiones lo es."""
    candidato = _SEPARADORES.sub("", dni)
    return candidato if _PATRON.match(candidato) else None


def diagnosticar(filas: Iterable[FilaUsuario]) -> Informe:
    informe = Informe()
    por_dni: dict[str, list[FilaUsuario]] = defaultdict(list)
    for fila in filas:
        informe.total_con_dni += 1
        if _PATRON.match(fila.dni):
            informe.validos += 1
            por_dni[fila.dni].append(fila)
            continue
        if not fila.dni.strip():
            informe.hallazgos.append(Hallazgo(fila.id, fila.role, "", "vacio", "Cambiar a NULL (vacío = no enviado)."))
            continue
        normalizado = normalizar(fila.dni)
        if normalizado is not None:
            informe.hallazgos.append(Hallazgo(
                fila.id, fila.role, enmascarar(fila.dni), "normalizable",
                f"Guardar sin separadores ({enmascarar(normalizado)}), si no choca con otra cuenta.",
            ))
            por_dni[normalizado].append(fila)  # detecta choques que aparecerían al normalizar
            continue
        informe.hallazgos.append(Hallazgo(
            fila.id, fila.role, enmascarar(fila.dni), "invalido",
            "Pedir al usuario que corrija su DNI (o dejarlo en NULL para que lo regularice).",
        ))
    for dni, filas_dni in sorted(por_dni.items()):
        if len(filas_dni) > 1:
            informe.duplicados.append(GrupoDuplicado(
                dni_enmascarado=enmascarar(dni),
                usuarios=[{"id": f.id, "role": f.role, "created_at": f.created_at} for f in filas_dni],
            ))
    return informe


def formatear(informe: Informe) -> str:
    lineas = [
        "Diagnóstico de users.dni (solo lectura)",
        f"- Usuarios con DNI: {informe.total_con_dni}",
        f"- Con formato válido: {informe.validos}",
        f"- Inválidos o por normalizar: {len(informe.hallazgos)}",
        f"- DNI repetidos: {len(informe.duplicados)} grupos",
        f"- Listo para la migración del índice único: {'sí' if informe.listo_para_migrar else 'no'}",
    ]
    if informe.hallazgos:
        lineas.append("")
        lineas.append("Inválidos o por normalizar:")
        for h in informe.hallazgos:
            lineas.append(
                f"  [{h.categoria}] usuario {h.id} ({h.role}) DNI {h.dni_enmascarado or '(vacío)'}: {h.sugerencia}"
            )
    if informe.duplicados:
        lineas.append("")
        lineas.append("DNI repetidos:")
        for g in informe.duplicados:
            cuentas = ", ".join(f"{u['id']} ({u['role']}, {u['created_at']})" for u in g.usuarios)
            lineas.append(f"  DNI {g.dni_enmascarado}: {cuentas}")
        lineas.append(f"  Qué hacer: {SUGERENCIA_DUPLICADO}")
    return "\n".join(lineas)


async def _leer_filas() -> list[FilaUsuario]:
    from sqlalchemy import text

    from app.core.db import engine

    try:
        async with engine.connect() as conexion:
            await conexion.execute(text("SET TRANSACTION READ ONLY"))
            resultado = await conexion.execute(
                text("SELECT id, role, dni, created_at FROM users WHERE dni IS NOT NULL ORDER BY created_at")
            )
            filas = [FilaUsuario(str(r.id), r.role, r.dni, r.created_at.isoformat()) for r in resultado]
            await conexion.rollback()
    finally:
        await engine.dispose()
    return filas


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnóstico de DNI inválidos o duplicados (solo lectura).")
    parser.add_argument("--json", action="store_true", help="informe en JSON")
    args = parser.parse_args()
    informe = diagnosticar(asyncio.run(_leer_filas()))
    if args.json:
        datos = asdict(informe) | {"listo_para_migrar": informe.listo_para_migrar}
        print(json.dumps(datos, ensure_ascii=False, indent=2))
    else:
        print(formatear(informe))


if __name__ == "__main__":
    main()
