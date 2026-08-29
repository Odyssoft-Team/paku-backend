# Dominio — <Entidad>

> Módulo backend: `app/modules/<módulo>/`
> Estado del doc: ⬜ pendiente
> Última verificación contra código: —

## Qué es

Una o dos frases.

## Modelo

Campos relevantes, tipos, invariantes. No copiar el ORM entero; solo lo que importa para entender reglas.

## Estados y transiciones

```
estado_a → estado_b → estado_c
```

Quién dispara cada transición (usuario / ally / admin / sistema).

## Reglas de negocio

- Regla 1
- Regla 2

## Endpoints

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/…` | user | … |

Errores de negocio: código → significado.

## Consumidores

Qué hace cada cliente con esta entidad.

- **paku-web**: …
- **paku-admin**: …
- **paku-vet-dev**: …

## Preguntas abiertas

- [ ] …
