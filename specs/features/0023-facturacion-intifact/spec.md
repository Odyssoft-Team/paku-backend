---
feature: 0023-facturacion-intifact
estado: in-progress
repos: [paku-backend, paku-admin]
creado: 2026-11-26
reemplaza: 0020-boletas-nubefact
---

# Facturación electrónica con Intifact

## Problema

Paku cobra sus servicios (tarjeta, Yape o efectivo) y debe entregar un comprobante electrónico válido ante SUNAT
por cada cobro. La integración con Nubefact (0020) quedó en la fase de conexión y se abandona: el proveedor es
**Intifact** (`https://api-facturacion.intifact.com/api/v1`, documentación en `docs.intifact.com/docs/facturacion`),
el mismo que ya usa Dulce Recuerdo con boletas y facturas.

## Objetivo

Una sección «Facturación electrónica» en el admin desde la que se emiten, consultan, descargan y anulan boletas y
facturas de las órdenes pagadas. Incluye la configuración de Intifact, las series, los reportes para el contador y el
comprobante visible para el cliente.

## Fuera de alcance

- Notas de crédito y débito: Intifact no documenta el cuerpo de `POST /note/send`. Pasados los 7 días para anular,
  se registra como pendiente.
- Guías de remisión, detracciones, ventas en dólares, exportación.
- Pedir RUC desde la app de clientes: la factura la emite el admin con los datos que da el cliente.
- Importar clientes de otro sistema (el SUSII de Dulce Recuerdo no aplica a Paku).

## Reglas

1. **Qué se factura:** cada orden **pagada** (`payment_status = paid`) lleva su propio comprobante, sea de servicio
   o de ajuste por diferencia de peso (el ajuste se cobra aparte y se factura aparte). Las órdenes canceladas no
   aparecen como pendientes.
1b. **Cuándo está lista para emitir** (dueño, 2026-11-26): lo define el **momento de emisión** de Configuración →
   Intifact. **Al realizarse el servicio** (por defecto): la orden de servicio debe estar realizada (`done`) y el
   ajuste por peso, su orden original; así la boleta sale con la fecha del servicio (contratado el 30/11 y realizado
   el 01/12 → boleta del 01/12). **Al confirmarse el pago:** apenas está pagada. Una orden que no está lista no
   aparece en «Por emitir» ni se puede emitir (409 `ORDER_NOT_READY`).
2. **Un comprobante vigente por orden.** Vigente es cualquier estado salvo `RECHAZADO`, `ANULADO`, `ERROR` y
   `COLA_FALLIDA`: con uno de esos la orden vuelve a «por emitir».
3. **Montos:** los precios de Paku incluyen IGV (18 %, afectación 10 «gravado»). El total del comprobante es
   exactamente lo cobrado (`total_snapshot`). El descuento de campaña se reparte entre las líneas en proporción a su
   precio, así cada línea muestra lo que se pagó. Si el cálculo de Intifact no da el total cobrado, no se emite.
4. **Detalle:** una línea por servicio base, adicional o ajuste, con su nombre y el de la mascota.
5. **Cliente de la boleta:** DNI (8 dígitos), carné de extranjería, pasaporte o RUC. Con un DNI válido en el perfil
   se usa ese; sin documento se emite a consumidor final (`00000000`) **solo por debajo de S/ 700**. La factura
   exige RUC de 11 dígitos.
6. **Series:** 4 caracteres, `B…` para boletas y `F…` para facturas, con una serie activa por tipo. El correlativo
   es el mayor entre el inicial configurado, el último emitido aquí + 1 y el que propone Intifact, así nunca se
   repite un número usado por otro sistema.
7. **Anulación:** solo de comprobantes aceptados y hasta **7 días** después de emitidos. La factura se anula con
   comunicación de baja y la boleta con resumen diario. Después corresponde una nota de crédito (fuera de alcance).
8. **Ambiente:** lo decide la API key (`fact_test_…` es SUNAT beta, sin valor fiscal; `fact_live_…` es producción).
   Cada comprobante guarda su ambiente, y las series y los reportes cuentan solo el ambiente actual.
9. **Estado SUNAT:** se consulta al emitir. Después lo actualizan el webhook de Intifact (firma HMAC-SHA256,
   tolerancia de 5 minutos) y, como respaldo, una revisión automática cada 10 minutos de los comprobantes en curso.
   El webhook requiere plan de pago.
10. **Emisión automática (opcional, apagada por defecto):** emite, en el momento de emisión configurado, boletas de
    las órdenes listas sin comprobante que se pueden emitir sin intervención: cliente con DNI válido, o consumidor
    final por debajo de S/ 700. Las demás quedan pendientes para el admin. La emisión manual siempre está disponible:
    los modos no se excluyen (manual + automática al realizarse, o manual + automática al pagar).
10b. **Emisión de varias (admin):** en «Por emitir» se eligen varias órdenes listas y se emiten juntas (hasta 50), con
    un resumen antes de enviar. Solo boletas con los datos del perfil (como la automática); las que necesitan datos del
    admin se emiten de a una. Se envían una a la vez y un error no detiene las demás.
11. **Al cliente:** cuando SUNAT acepta, se le envía un correo con el número, el total y el enlace público del PDF.
    En la app puede ver los comprobantes de su orden y descargar el PDF.

## Comportamiento esperado

1. **Dado** Intifact configurado y una serie B activa, **cuando** el admin pide la vista previa de una orden pagada,
   **entonces** ve el número que tendría, las líneas, la base, el IGV y el total, sin que se envíe nada a SUNAT.
2. **Dado** lo mismo, **cuando** emite, **entonces** se envía a Intifact, se guarda el comprobante con su estado y la
   orden deja de estar pendiente.
3. **Dado** una orden con comprobante vigente, **cuando** se intenta emitir otro, **entonces** responde 409.
4. **Dado** una boleta de S/ 700 o más sin documento, **entonces** responde 422.
5. **Dado** un comprobante aceptado hace más de 7 días, **cuando** se anula, **entonces** responde 409 e indica que
   corresponde una nota de crédito.
6. **Dado** un aviso del webhook con firma válida, **entonces** el estado se actualiza. Con firma inválida o vencida
   responde 401.
7. **Dado** un mes con comprobantes, **entonces** el admin descarga el resumen de totales (xlsx), el resumen de
   facturas (xlsx), el compendio de PDF (zip) y el registro de ventas PLE 14.1 (txt).
8. **Dado** el momento «al realizarse el servicio», **cuando** una orden está pagada pero el servicio no se realizó,
   **entonces** no aparece en «Por emitir» y emitirla responde 409 `ORDER_NOT_READY`; al pasar a realizada, aparece
   (y si la emisión automática está activa, se emite sola).
9. **Dadas** varias órdenes listas elegidas, **cuando** el admin las emite juntas, **entonces** se emiten las boletas
   que no necesitan datos y las demás vuelven con su motivo (`NEEDS_CUSTOMER_DATA`, `ORDER_NOT_READY`…).

## Criterios de aceptación

- [x] Configuración de Intifact con la API key y el secreto del webhook cifrados, más una prueba de conexión.
- [x] Series con correlativo inicial y una activa por tipo.
- [x] Pendientes de emitir, vista previa, emisión, registro con filtros, detalle, PDF, XML, CDR y anulación.
- [x] Directorio de clientes de facturación (usuarios con documento y empresas con RUC) y autocompletar.
- [x] Webhook firmado y revisión periódica de los comprobantes en curso.
- [x] Emisión automática opcional.
- [x] Reportes contables por mes.
- [x] Endpoints del cliente: comprobantes de su orden y PDF.
- [ ] Probado contra Intifact con una key `fact_test_` (requiere la key del dueño).

## Impacto en el dominio

Entidades nuevas: comprobante electrónico, serie y empresa cliente. La orden no cambia: el comprobante la referencia.

## Preguntas abiertas (supuestos tomados; revisables)

- [x] ¿La emisión es al cobrar, o al terminar el servicio? **Configurable; por defecto al realizarse el servicio**
      (dueño, 2026-11-26). Pendiente: confirmar con el contador si un cobro anticipado (tarjeta o Yape antes del
      servicio) obliga a emitir al cobrar; si es así, usar «al confirmarse el pago».
- [ ] ¿El ajuste por peso va en su propio comprobante? Supuesto: **sí**, porque se cobra aparte.
- [ ] ¿El descuento de campaña debe verse como descuento en el comprobante? Supuesto: **precio rebajado por línea**.
- [ ] Confirmar con el contador el IGV de los servicios (gravado 18 %, precios con IGV).
- [ ] ¿Se activa la emisión automática desde el inicio?
