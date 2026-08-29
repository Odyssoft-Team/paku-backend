# Paku — Spec-Driven Development

Fuente de verdad del producto Paku. El código implementa lo que está aquí; si divergen, es un bug a reconciliar.

## Regla de oro

Antes de escribir código para una feature nueva o un cambio de comportamiento:
1. Existe un **spec** aprobado (`features/NNNN-slug/spec.md`).
2. Existe un **plan** (`features/NNNN-slug/plan.md`).
3. Existen **tasks** (`features/NNNN-slug/tasks.md`).

Bugfixes triviales y refactors sin cambio de comportamiento no necesitan spec.

## Estructura

```
specs/
  README.md          ← este archivo
  constitution.md    ← reglas invariantes para TODOS los repos Paku
  workspace.md       ← mapa de los 4 repos (contexto de arranque de sesión)
  api/
    README.md        ← contrato de API: convenciones + OpenAPI como fuente de forma
  domain/
    README.md        ← índice de entidades del dominio + estado
    _template.md
    <entidad>.md     ← una por entidad compartida (orders, cart, pets, booking…)
  features/
    README.md        ← flujo y numeración
    _template/        ← spec.md · plan.md · tasks.md
    NNNN-slug/
```

`paku-backend` es el canon del **dominio y la API**. `paku-web`, `paku-admin` y `paku-vet-dev`
tienen su propio `specs/` para features y estado **de ese cliente**, y referencian este por nombre de ruta
(ej. `paku-backend/specs/domain/orders.md`). Los repos son hermanos en el mismo workspace.

## Flujo de una feature

| Fase | Archivo | Pregunta que responde | No incluye |
|------|---------|----------------------|------------|
| Specify | `spec.md` | Qué y por qué. Criterios de aceptación. | Cómo, nombres de archivos, tech |
| Plan | `plan.md` | Cómo. Archivos, contratos, migraciones, riesgos. | Código |
| Tasks | `tasks.md` | Checklist ejecutable y verificable. | — |
| Implement | (código + PR) | — | — |

Cada fase se revisa antes de pasar a la siguiente.

## Comando

`/spec <slug>` (skill en `.claude/`) arranca el flujo: crea `features/NNNN-slug/` desde `_template/`.
