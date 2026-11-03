---
feature: 0020-boletas-nubefact
estado: in-progress
repos: [paku-backend, paku-admin]
creado: 2026-11-02
---

# Boletas de venta con Nubefact

## Problema

Paku necesita emitir boletas electrónicas ante SUNAT por sus ventas. Nubefact es el proveedor elegido; antes de
emitir hay que conectar la cuenta y tener claro qué permite su API y qué falta decidir.

## Objetivo (fase 1, esta entrega)

Configuración → Integraciones: conexión real con Nubefact (ruta, token cifrado, serie de boletas, activo, probar
conexión sin emitir) y una vista «Qué se puede hacer» con lo posible, lo imposible y lo que falta decidir, según el
manual de la API JSON de Nubefact y los datos de Paku (RUC, IGV, clientes con DNI).

## Fuera de alcance (fase 1)

Emitir, consultar, anular o enviar comprobantes; notas de crédito o débito; facturas.

## Lo que dice el manual de Nubefact (API JSON)

- RUTA única por cuenta + TOKEN; todo por POST a la RUTA, `Authorization: <token>`, `Content-Type: application/json`.
- Operaciones: `generar_comprobante`, `consultar_comprobante`, `generar_anulacion`, `consultar_anulacion`.
- `tipo_de_comprobante`: 1 factura, 2 boleta, 3 nota de crédito, 4 nota de débito. Serie de boletas: 4 caracteres
  que empiezan con «B»; número correlativo desde 1, sin ceros a la izquierda.
- Errores: 10 token, 11 ruta, 12 Content-Type, 20 formato, 21 operación, 22 fuera de plazo, 23 ya existe, 24 no
  existe, 40 interno, 50/51 cuenta suspendida.
- `fecha_de_emision` debe ser la del día. No hay operación para listar comprobantes. Sin URL de pruebas: cuenta DEMO
  y documentos de prueba antes de producción.
- El manual no indica el plazo para anular boletas ni el monto desde el que se exige DNI (ver «Por decidir»).

## Comportamiento esperado

1. **Dado** ruta y token válidos, **cuando** se prueba la conexión, **entonces** se consulta la boleta
   `{serie}-99999999` y la respuesta «no existe» (24) cuenta como conexión correcta. Nunca se llama a
   `generar_comprobante`.
2. **Dado** un token o ruta incorrectos o la cuenta suspendida, **entonces** la prueba falla con el motivo del
   código de error.
3. El token se guarda cifrado y solo se muestra enmascarado; vacío conserva el guardado.

## Por decidir antes de emitir (fase 2)

- Cuándo se emite (pago confirmado o servicio terminado).
- Cliente sin DNI: SUNAT exige identificar al comprador en boletas de más de S/ 700 (confirmar con el contador).
- Cargos extra por diferencia de peso (orden de ajuste): boleta aparte o una sola.
- Descuentos de campaña: descuento en la boleta o precio rebajado.
- IGV de los servicios (gravado con IGV incluido, a confirmar con el contador).
- Quién envía la boleta al cliente (Nubefact, correo de Paku o solo en la app).
- Plazo para anular boletas (el manual no lo indica; error 22).

## Criterios de aceptación (fase 1)

- [x] Token cifrado y enmascarado; validación todo o nada con `field`.
- [x] Prueba de conexión que no emite.
- [x] Vista de capacidades con estado real de Paku.
- [ ] Probado con la cuenta real (o DEMO) de Nubefact.
