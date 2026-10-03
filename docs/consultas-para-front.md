# Consultas para el front

Preguntas abiertas del backend a los equipos de front. Mientras no haya respuesta, el backend
aplica el supuesto indicado (ver también `plan-de-trabajo.md`).

| # | Pregunta | App | Supuesto actual del backend |
|---|---|---|---|
| 1 | ¿Alguna app usa `PATCH /orders/{id}`? ¿Para qué? | Todas | Queda solo para admin y groomer asignado. Si nadie lo usa, se elimina. |
| 2 | La app de clientes, ¿es web o se instala desde tiendas (iOS/Android)? | Clientes | Afecta el despliegue del renombre `ally` → `groomer`: si es de tiendas, los teléfonos con la versión vieja verán campos que ya no existen hasta actualizar. |
| 3 | ¿Qué formato de addons envían hoy al carrito: líneas `service_addon` separadas (`meta.base_service_id` / `meta.requires_base`) o `meta.addon_ids` dentro del servicio base? | Clientes | El backend acepta las líneas `service_addon` (formato único, ver cambios) e ignora esas claves de `meta`. |
| 4 | ¿Se venden productos físicos (ítems `kind=product`) en el carrito? | Clientes / Admin | No: `store` no tiene precios para productos físicos y el backend los rechaza. |
| 5 | ¿Usan `POST /cart/{id}/items` (agregar de a un ítem) o solo `POST /cart/items` y `PUT /cart/{id}/items` (lote)? | Clientes | Los tres validan y cotizan igual desde ahora. |
