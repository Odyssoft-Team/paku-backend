---
feature: 0004-precios-por-pelaje
estado: in-progress   # draft | approved | in-progress | done | abandoned
repos: [paku-backend, paku-admin]
creado: 2026-10-13
---

# Precios por tipo de pelaje y tabla de precios del admin

## Problema

Desde 2026-09-04 la cotización clasifica a la mascota como "official" / "otros" / "mestizo", pero el
admin carga y muestra las reglas por **tipo de pelaje**. Resultado (datos de 2026-10-13, PAKU Spa):

- Las 36 reglas por pelaje de Clásico no se usan: todos pagan la fila "mestizo".
- Premium solo tiene 5 reglas: una mascota de raza a 10 kg paga S/65 (Clásico S/90).
- Express solo tiene reglas "otros": razas del catálogo y mestizos no tienen precio.
- El admin no puede crear reglas nuevas: ofrece pelajes y la API solo acepta official/otros/mestizo.
- La tabla del admin no muestra qué regla aplica ni compara productos.

## Objetivo

Que el precio dependa del **tipo de pelaje** de la raza (el trabajo del groomer) y del peso, y que el
admin gestione cada producto como una tabla pelaje × peso, compare productos y simule precios.

## Fuera de alcance

- Cambiar los tramos de peso existentes o el modelo de reglas (tabla `store_price_rules`).
- Precios para gatos (hoy no hay productos para gatos; se cotizan con la fila "mestizo").
- Definir los montos de Premium, Express y addons (los define el negocio en la nueva pantalla).

## Comportamiento esperado

1. **Dado** un perro de raza del catálogo (p. ej. Labrador), **cuando** se cotiza, **entonces** se usa
   la fila de su tipo de pelaje (Doble manto corto) y el tramo de su peso.
2. **Dado** un mestizo, una raza escrita a mano o sin raza, **entonces** se usa la fila "mestizo".
3. **Dado** que el producto no tiene precio para ese pelaje, **entonces** se usa su fila "mestizo".
4. **Dado** el admin, **cuando** guarda la tabla de un producto/addon, **entonces** se reemplazan sus
   reglas activas en una sola operación (las anteriores quedan inactivas como historial).
5. **Dado** una tabla con tramos solapados, precios negativos o categorías desconocidas, **entonces**
   se rechaza con 422 y un código (`WEIGHT_RANGE_OVERLAP`, `PRICE_INVALID`, `PRICE_CATEGORY_INVALID`…).
6. **Dado** el admin, **cuando** simula raza + peso, **entonces** ve la categoría aplicada y el precio de
   cada producto y addon, indicando si se usó el respaldo "mestizo".

## Criterios de aceptación

- [x] Cotización, catálogo y saldo por peso usan la categoría por pelaje.
- [x] `POST /admin/store/price-rules` acepta los 6 pelajes + "mestizo".
- [x] `GET /admin/store/price-config`, `PUT /admin/store/price-matrix/{id}`, `GET /admin/store/price-simulation`.
- [x] Tests pytest.
- [ ] Pantalla de precios en paku-admin (tabla, comparar, alertas, simulador, edición rápida).
- [ ] Tablas completas de Premium, Express y addons cargadas por el negocio.

## Impacto en el dominio

Sin cambios de esquema. Las reglas "official"/"otros" existentes quedan sin uso (el admin las muestra
como antiguas para desactivarlas).
