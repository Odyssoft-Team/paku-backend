---
feature: 0011-clientes-crm
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin]
creado: 2026-10-29
---

# Clientes: gasto, frecuencia, última visita y segmento

## Problema

El admin tiene una maqueta de CRM · Clientes (lista, tarjetas y ficha) con datos de ejemplo. Hoy, para algo
parecido, el admin tendría que traer todos los usuarios y todas las órdenes y calcular en el front (lo que
ya hace Órdenes para mostrar nombres). La maqueta misma pide "un endpoint de resumen por cliente".

## Objetivo

El backend calcula, por cada dueño con servicios, cuánto gastó, cuántos servicios tuvo, cada cuánto viene,
cuándo vino por última vez y su segmento, y da la ficha con mascotas e historial.

## Fuera de alcance

- Campañas, fidelización, recordatorios e integraciones del CRM (otras maquetas).
- Descuentos y devoluciones: el backend no los tiene todavía.
- Paginación (como el resto del admin; hoy son pocos clientes).

## Comportamiento esperado

1. **Dado** un dueño, **entonces** sus servicios son sus órdenes de servicio terminadas (`done`, sin orden
   padre). Canceladas, en curso y sin terminar no cuentan.
2. **Dado** un servicio, **entonces** su monto es lo pagado: la orden si está pagada más sus cargos extra
   pagados. El gasto es la suma; el ticket promedio, gasto ÷ servicios.
3. **Dado** el día de cada servicio (cuando terminó, en hora de Lima), **entonces** frecuencia = días entre
   la primera y la última visita ÷ (días distintos − 1); sin frecuencia si hay un solo día.
4. **Dado** un cliente, **entonces** su segmento, en este orden: `inactivo` (> 75 días sin venir),
   `en_riesgo` (más de max(45, 1,5 × frecuencia) días), `nuevo` / `sin_recompra` (un servicio, hace ≤ 30 o
   más días), `vip` (5 o más servicios en 180 días), si no `recurrente`.
5. **Dado** el listado, **entonces** solo aparecen dueños con al menos un servicio; se filtra por segmento,
   distrito, texto (nombre, correo, teléfono o mascota, sin importar tildes) y rango de última visita, y se
   ordena por gasto, última visita o servicios.
6. **Dado** el distrito, **entonces** es el de la dirección principal; si no, el del perfil; si no, el del
   último servicio.
7. **Dada** la ficha, **entonces** trae las mascotas (con tramo de peso y servicios de cada una) y el
   historial de servicios (servicio, adicionales, mascota, monto), también para un cliente sin servicios.
8. **Dadas** las estadísticas, **entonces** clientes, mascotas, activos (≤ 45 días), con recompra, gasto
   total y promedio, y cuántos hay en cada segmento con su regla.

## Criterios de aceptación

- [x] `GET /admin/customers`, `GET /admin/customers/stats`, `GET /admin/customers/{user_id}`.
- [x] Reglas de segmento de la maqueta en el backend.
- [x] Sin migración; tests.

## Impacto en el dominio

Módulo nuevo `crm`, solo lectura sobre `iam`, `pets` y `orders`.

## Supuestos (decididos sin preguntar, revisables)

- **Reglas de segmento** = las de la maqueta (umbrales 30, 45, 75, 180 días y 5 servicios). Son constantes en
  `crm/domain/customers.py`, fáciles de ajustar.
- **Gasto = lo pagado.** Una orden terminada sin pagar cuenta como servicio pero no suma al gasto.
- **Un servicio por orden**, aunque el mismo día haya dos mascotas (dos órdenes = dos servicios).

## Preguntas abiertas

- [ ] ¿Se aprueban las reglas de segmento de la maqueta?
- [ ] ¿Usuarios (lista actual del admin) y Clientes conviven o Clientes la reemplaza para el rol `user`?
