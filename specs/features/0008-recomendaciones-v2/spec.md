---
feature: 0008-recomendaciones-v2
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-monorepo, paku-admin]
creado: 2026-10-15
---

# Recomendaciones determinísticas, fotos previas y revisión del admin (documento V2)

## Problema

La versión 2 del documento de precios (`PAKU_Pricing_Logica_App_V2_Recomendaciones.xlsx`) agrega un motor de
recomendaciones sin IA (hojas 17–20) y pendientes de go-live (hoja 21). Decisiones del cliente (2026-10-15):

1. No cobrar la diferencia de peso: se respeta el precio pagado y el peso real queda para el futuro (BR-029).
2. Express sin agua: solo Cepillo dental personal (hoja 18, AR-001).
3. Manto muy apelmazado: se permite reservar y el admin aprueba antes del servicio (AR-022).
4. Reglas fijas por ahora (sin editor en el admin), pero como datos: se cambian en la BD sin tocar código.
5. REC-005 activa: S3 → Spa Deluxe salvo piel sensible (gana REC-002 → Cuidado Especial). Solo recomienda;
   el precio sigue siendo servicio × pelaje × peso.

## Comportamiento esperado

1. `POST /store/recommendations` devuelve el servicio recomendado (regla de menor prioridad que aplica y cuyo
   servicio la mascota puede comprar), las preguntas que aplican a su pelaje y servicio, y el estado de cada
   adicional (recomendado, ofrecido, disponible). Los no disponibles no se devuelven.
2. Respuestas solo con códigos conocidos (BR-028); 422 `ANSWER_INVALID` si no.
3. El carrito guarda en la línea del servicio las respuestas y la recomendación (versión, reglas, si eligió
   el recomendado, si requiere fotos o revisión) — BR-030.
4. Corte estético, Desmotado extendido o revisión manual exigen fotos: el cliente sube fotos `pre_service` a
   su orden; `POST /orders/{id}/pay` sin fotos → 409 `PHOTOS_REQUIRED`.
5. Revisión manual: la orden nace con `review_status = pending`; no se puede asignar (409 `REVIEW_PENDING`)
   hasta que el admin la apruebe (`POST /admin/orders/{id}/review`). Rechazar cancela la orden y libera el cupo.
6. El peso registrado en el servicio ya no genera cobro ni aviso (sigue en la orden y en el perfil).

## Fuera de alcance

Editor de reglas en el admin, duración por servicio/adicional (pendiente del cliente), devolución automática
al rechazar (pendiente del cliente).
