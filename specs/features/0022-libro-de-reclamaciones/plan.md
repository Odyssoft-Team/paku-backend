---
feature: 0022-libro-de-reclamaciones
spec: ./spec.md
---

# Plan — Libro de Reclamaciones

## Backend

- Módulo `app/modules/complaints` (api / app / domain / infra).
- Migración `9a0b1c2d3e4f`: tablas `complaints` y `complaint_counters` (correlativo por año con `FOR UPDATE`
  y restricción única `(year, number)`).
- `POST /complaints` (público, límite por IP holgado), `GET /admin/complaints`, `GET /admin/complaints/{id}`,
  `POST /admin/complaints/{id}/answer`.
- Correos con `messaging.send_email` (idempotentes: `complaint:copy|notify|answer:{id}`); el HTML escapa todo.
- Parámetros generales: razón social, domicilio y correo de reclamos con valores por defecto.

## Web (paku-web)

- `/libro-de-reclamaciones`: formulario que llama a `POST /complaints` y muestra la constancia (imprimible).
- Quitar los enlaces a plataformas externas; el pie de página apunta a la página propia.

## Admin (paku-admin)

- Pantalla «Libro de Reclamaciones»: lista con estado y vencidas, detalle con la hoja y formulario de respuesta.

## Riesgos

- Si el correo (Resend) no está configurado, la hoja se guarda pero la copia no sale: configurar antes de publicar.
- Detrás de un proxy, el límite por IP agrupa a todos; por eso es holgado (20 por hora).
