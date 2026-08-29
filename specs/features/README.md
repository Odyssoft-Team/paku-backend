# Features

Una carpeta por feature: `NNNN-slug/` con `spec.md`, `plan.md`, `tasks.md`.

## Numeración

`NNNN` = correlativo global de 4 dígitos (`0001`, `0002`…), **por repo**.
El slug es corto y en kebab-case: `0007-culqi-checkout`.

## Ciclo de vida

1. `spec.md` — se escribe y se aprueba. Sin tech, sin código.
2. `plan.md` — se escribe y se aprueba. Cómo, archivos, riesgos.
3. `tasks.md` — checklist. Se marca durante la implementación.
4. Implementación → PR que referencia `specs/features/NNNN-slug/`.
5. Al mergear: `spec.md` pasa a estado `done`. Si cambió algo, se actualiza el spec (es el canon).

## Estado (frontmatter en spec.md)

`draft` → `approved` → `in-progress` → `done` · o `abandoned`.

## Índice

| # | Feature | Repo(s) | Estado |
|---|---------|---------|--------|
| — | (ninguna todavía) | | |

## Cross-repo

Una feature puede tocar varios repos. Vive en el `specs/` del repo donde está el grueso del trabajo;
si es dominio/API, va en `paku-backend`. El `plan.md` lista el impacto en cada repo.
