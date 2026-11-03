---
feature: 0019-simulador-servicio
estado: in-progress
repos: [paku-backend, paku-admin]
creado: 2026-11-02
---

# Simulador de un servicio

## Problema

Para revisar recetas y precios, el admin necesita ver cuánto consume y cuánto cuesta un servicio concreto (servicio,
adicionales, raza y peso) sin esperar a que exista una orden terminada.

## Objetivo

Inventario → Recetas y costeo → «Simulador de servicio»: elegir servicio, adicionales, raza, peso y (opcional)
groomer, y ver la celda de receta usada, el consumo de cada insumo frente al stock de hoy, minutos, mano de obra,
precio y margen.

## Fuera de alcance

Registrar consumos, crear órdenes, guardar simulaciones, comparar varias a la vez.

## Comportamiento esperado

1. **Dado** un servicio con receta y precio, **cuando** se elige raza y peso, **entonces** se usa la celda del pelaje
   de la raza (o «mestizo» si falta) y el tramo del peso, igual que en una orden real.
2. **Dado** que no se elige raza, **entonces** se usa la fila «mestizo».
3. **Dado** adicionales, **entonces** suman sus insumos, minutos y precio.
4. **Dado** un ítem sin receta o sin precio para ese pelaje y peso, **entonces** se avisa y el precio total o el margen
   quedan sin calcular (no se inventan).
5. **Dado** el stock de hoy, **entonces** cada insumo muestra cuántos servicios iguales alcanzan, y el total es el del
   insumo que primero se acaba.
6. **Dado** un groomer elegido, **entonces** la mano de obra usa su costo por hora; si no, el de referencia.
7. **Dado** un peso mayor al máximo del servicio, **entonces** se simula igual y se avisa que en la app no se podría
   comprar.

## Criterios de aceptación

- [x] Mismas reglas que el costeo de una orden (`plan_consumption`, `price_for`, `LaborRates`).
- [x] No registra nada.
- [ ] Revisado en el navegador con recetas reales.
