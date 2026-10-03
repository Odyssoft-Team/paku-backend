# Pendientes

Temas identificados que no se resuelven en la etapa actual. "Por decidir" requiere una decisión
del dueño; "Para después" ya está entendido y se programa más adelante.

## Por decidir

- **Un carrito, ¿una sola orden?** Hoy un carrito `checked_out` permite crear varias órdenes con
  `POST /orders` (el carrito no queda marcado como usado). Decidir si un carrito genera una sola orden.
- **Reserva por día ↔ orden.** El booking reserva cupo por día (`/holds`), pero la orden no queda
  ligada a la reserva (`hold_id` nunca se asigna) y la fecha del carrito no se valida contra la
  disponibilidad. Decidir cómo se conectan.

## Configuración del servidor (no es código)

- **`GOOGLE_ROUTES_API_KEY`** (pedido 7): no está en `.env` ni en `docker-compose.yml`. Sin ella
  `GET /tracking/orders/{id}/route` responde 501 y el mapa del groomer no muestra ruta/ETA.
- **Migraciones nuevas** `1a2b3c4d5e6f` → `2b3c4d5e6f7a` → `3c4d5e6f7a8b`: corren solas al arrancar el
  contenedor (`alembic upgrade head`). Probarlas antes en una copia de la BD.
- **Venv local** sin `firebase_admin` ni `PyJWT` (están en `requirements.txt`): `pip install -r requirements.txt`.
- **Tests de integración** (`tests/*.py`, necesitan Postgres) estaban desactualizados antes de este
  trabajo (usan el estado `in_process`, ítems `kind=product`, etc.). Los unitarios (`tests/unit`) están al día.

## Para después

- **Refresh token.** `POST /auth/refresh` emite un access token desde los datos del refresh token
  (30 días) sin consultar la BD: rol y estado activo pueden quedar desactualizados hasta 30 días y
  `profile_completed` se fuerza a `true` (se salta `require_profile_complete`). No hay rotación ni
  revocación. Además, la mayoría de endpoints confía en los datos del token en lugar de la BD, así que
  un usuario desactivado sigue entrando mientras su token sea válido.
- **Streaming.** Secretos y credenciales TURN con valores por defecto en `settings.py`; revisar
  junto con la configuración de producción.
- **Reset de contraseña.** El token se escribe en logs (nivel WARNING), puede reusarse durante
  15 minutos y no hay envío de correo.
- **Configuración por defecto insegura.** `SECRET_KEY` con valor por defecto, `DEBUG=true` por
  defecto (además vuelca SQL a los logs), CORS `*` por defecto. Verificar las variables de producción.
- **Transacciones.** Cada método de repositorio hace su propio commit; operaciones de varios pasos no
  son atómicas (ej. crear la orden y luego `order_pets`).
- **Rate limit de login en memoria por IP.** Detrás de nginx probablemente todos los clientes
  comparten IP (no verificado).
- **Integración con HCVet (etapa 2).** Ver `plan-de-trabajo.md`.
