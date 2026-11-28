---
feature: 0028-integracion-propietarios-hcvet
estado: in-progress   # PAKU-OWNERS-001 a 011 implementadas sin desplegar (rectificación D-105 de HCVet: sin evidencia de titularidad)
repos: [paku-backend, paku-web, paku-vet-dev]
creado: 2026-11-28
---

# Integración y vinculación de propietarios entre Paku y HCVet (bloque C)

Requerimientos: `specs/integracion-hcvet/PAKU-HCVET-REQUIREMENTS.md` §5, §6, §7 y §11 (estados e idempotencia), con
la **rectificación del 2026-11-28** sobre titularidad (HCVet D-105). Tareas: `PAKU-OWNERS-001` a `PAKU-OWNERS-011` en
`specs/integracion-hcvet/PAKU-HCVET-TASKS.md`. Contratos de HCVet: feature 0005 de HCVet con los agregados compatibles de
D-105 (`hcvet-backend/docs/INTEGRACION.md`).

## Problema

Paku ya pide un DNI válido y único y guarda los nombres legales (feature 0027), pero no tiene forma de registrar a sus
clientes en HCVet, de pedirles las autorizaciones para hacerlo ni de guardar su referencia en HCVet.

## Objetivo

Que el cliente decida, con consentimientos explícitos y con evidencia guardada, si Paku lo registra o lo vincula en
HCVet; que Paku lo haga sin contraseñas ni duplicados, guarde el identificador de HCVet y le avise los cambios de sus
datos básicos; y que todo funcione con HCVet caído, sin afectar las ventas de Paku.

## Fuera de alcance

- Mascotas (Pet) y eventos (Pet-records): bloques propios.
- Cualquier proceso de verificación de identidad o titularidad (presencial, biométrico, fotográfico): descartado.
- Pantalla de administración de la cola (hay API; la UI va en paku-admin cuando se pida).
- Migración masiva de usuarios existentes a HCVet (bloque de migración).

## Reglas

1. **Paku controla a sus usuarios.** Los datos viven en Paku; HCVet recibe solo lo autorizado. Ninguna reserva, orden
   o compra depende de HCVet (prueba que solo `iam` «Mi perfil», el scheduler y `main` importan el módulo).
2. **Solo el backend habla con HCVet**, con la API Key de Paku (`HCVET_API_KEY`, prefijo `hcv_`) fuera del
   repositorio. Los frontends llaman a Paku.
3. **Consentimientos explícitos**, ninguno por defecto, distintos entre sí:
   `integracion_hcvet` (autoriza a Paku a registrarlo o vincularlo y actuar con `ALCANCES_PAKU`),
   `indexacion_veterinaria` (compartir información veterinaria), `historial_compartido` (consultar la historia
   clínica), `registro_eventos` (registrar eventos) y `uso_comercial`. Rechazar cualquiera no limita Paku.
4. **Evidencia** de cada decisión, solo inserción: tipo, decisión, versión del texto, finalidad, canal (`web`/`app`),
   IP, agente de usuario y fecha. Una decisión sobre un texto que ya no es el vigente se rechaza (409).
5. **Textos provisionales** (`TEXTOS_APROBADOS = False`, versión `borrador-2026-11-28`): se aprueban antes de producción.
6. **Sin verificación de titularidad (D-105).** Paku no certifica que el DNI pertenece físicamente al cliente. La
   consulta a Datos Perú solo identifica el documento y autocompleta nombres y apellidos.
7. **Alta automática cuando corresponde:** con `integracion_hcvet` concedido, decisiones de indexación y uso comercial
   tomadas, DNI, nombres legales, teléfono válido, distrito y correo. No se envía evidencia.
8. **Sin duplicados ni contraseñas:** `POST /propietarios` con `Idempotency-Key`. Si el DNI ya existe (409), Paku se
   **vincula** con `POST /propietarios/{dni}/autorizaciones`; si esa autorización ya se creó en un intento sin
   respuesta, se recupera con `GET …/autorizaciones`.
9. **Vinculación ≠ acceso a lo preexistente (D-105).** Al vincularse a un propietario que ya existía, HCVet da acceso
   `basico`: Paku guarda el `propietario_id`, pero no ve ni cambia sus datos, mascotas, historiales ni consentimientos
   previos, y no le envía actualizaciones ni consentimientos. Pasa a `completo` solo por decisión del dueño, con su
   sesión en HCVet o comunicada por **otra** plataforma con acceso completo y `autorizacion.otorgar` (HCVet D-106); el
   dueño no necesita cuenta y Paku nunca se da acceso completo a sí mismo (no pide ese alcance). Paku lo detecta con
   una revisión cada 6 horas y entonces registra las decisiones del cliente.
   Conocer un DNI no da acceso a información ajena.
9b. **Referencia en Paku:** `hcvet_vinculos` guarda `hcvet_propietario_id`, `hcvet_autorizacion_id`, el DNI vinculado y
   el `acceso`. Con el vínculo vigente el DNI no se cambia en «Mi perfil» (409 `DNI_LOCKED_BY_HCVET`).
10. **Actualización controlada:** solo teléfono y nombres legales, con `datos_al`; los nombres con su verificación por
    campo (Datos Perú, D-095). El nombre visible nunca viaja. 409 de HCVet → `conflicto`, sin sobrescribir ni reintentar.
11. **Revocación:** cancela lo pendiente, envía primero los consentimientos ya encolados y luego revoca la autorización
    de Paku en HCVet. No borra nada en HCVet. Volver a autorizar crea una nueva alta (que termina en vinculación).
12. **Outbox y reintentos:** operaciones en `hcvet_operaciones` en la misma transacción; un job cada minuto las envía.
    Temporal (timeout, red, 5xx, 429 con `Retry-After`) → reintento con espera 1, 5, 15, 30, 60, 120, 240 min, hasta 8
    intentos. 401/403/404/422 → `fallido` sin reintento. 409 → `conflicto`. Colgada más de 10 min → se retoma con la
    misma clave. Las operaciones que dependen del vínculo esperan sin gastar intentos.
13. **Lo pendiente no se muestra como confirmado:** `vinculado` solo tras la respuesta de HCVet.
14. **Sin datos personales en errores ni logs:** se ocultan números largos y correos; la cola no guarda valores.
15. **Interruptor:** `HCVET_INTEGRACION_ACTIVA=false` por defecto: se guardan decisiones y operaciones, no se envía nada.

## Titularidad (rectificado el 2026-11-28, HCVet D-105)

El bloqueo anterior (PAKU-OWNERS-004) queda **eliminado**: el requerimiento se rectificó y no se implementa ningún
proceso de verificación de identidad. La protección contra el acceso a información ajena la da el acceso `basico` de
HCVet al vincularse a un propietario existente.

**Riesgo aceptado:** si alguien registra primero en Paku un DNI ajeno que no existía en HCVet, crea ese propietario con
sus datos. El titular real que llegue después (por otra plataforma o por cuenta propia) choca con el DNI y se resuelve
por soporte. Paku conserva la evidencia de los consentimientos (canal, IP, agente, fecha) para esa revisión.

## Escenarios

1. Dado un cliente sin decisiones, cuando abre «Historial clínico», entonces ve los cinco textos sin ninguna opción marcada y el estado `sin_autorizar`.
2. Dado un texto cambiado, cuando el cliente envía una decisión con la versión anterior, entonces 409 `CONSENT_TEXT_OUTDATED` y no se guarda nada.
3. Dada una decisión, cuando se guarda, entonces queda una fila con tipo, decisión, versión, finalidad, canal, IP, agente y fecha; repetir la misma decisión no agrega filas.
4. Dado un cliente que concede `integracion_hcvet`, entonces se crea su vínculo `pendiente` y una sola alta encolada.
5. Dado un cliente que rechaza todo, entonces no se encola nada y puede reservar igual.
6. Dado un cliente con datos completos, cuando corre el job, entonces se envía el alta sin `verificacion` (D-105).
7. Dado que faltan teléfono, distrito o nombres legales, entonces el alta queda `bloqueado`/`DATOS_INCOMPLETOS` con la lista de lo que falta.
8. Dada la integración apagada, entonces no se envía nada y el estado informa `INTEGRACION_INACTIVA`.
9. Dado un alta que HCVet acepta (201), entonces se guardan `hcvet_propietario_id` y `hcvet_autorizacion_id` y el vínculo pasa a `vinculado` con acceso `completo`; el cuerpo lleva nombres legales, alcances explícitos y consentimientos, sin evidencia, contraseña ni nombre visible.
10. Dado un DNI que ya existe en HCVet (409), entonces Paku se vincula con `POST …/autorizaciones` sin evidencia ni otro propietario; queda `vinculado` con acceso `basico` y el `propietario_id`, sin encolar consentimientos.
10b. Dado un vínculo básico, entonces no se encolan actualizaciones ni consentimientos, y el front explica que lo registrado antes por otras veterinarias no se comparte sin la autorización del dueño en HCVet.
10c. Dado un vínculo básico, cuando la revisión periódica encuentra una autorización vigente `completo` (el dueño la amplió con su sesión o por medio de otra plataforma), entonces el vínculo pasa a `completo` y se encolan los consentimientos del cliente; si no hay autorización vigente, el vínculo queda `fallido`/`AUTORIZACION_NO_VIGENTE`.
11. Dada una autorización creada en un intento sin respuesta, cuando la vinculación responde 409, entonces se recupera la vigente.
12. Dado un 5xx, timeout o error de red, entonces la operación queda `fallido` reintentable y se reintenta con la misma `Idempotency-Key`; el front sigue viendo `pendiente`.
13. Dado un 429 con `Retry-After`, entonces el reintento no ocurre antes de ese plazo.
14. Dados 8 fallos temporales, entonces la operación queda `fallido`/`REINTENTOS_AGOTADOS` y el vínculo `fallido`.
15. Dado un 401, 403 o 422, entonces la operación queda `fallido` sin reintento automático; el admin puede reencolarla.
16. Dada una operación colgada en `sincronizando` más de 10 minutos, entonces se retoma con la misma clave.
17. Dada una actualización sin vínculo confirmado, entonces espera (`ESPERA_VINCULO`) sin gastar intentos.
18. Dado un cliente vinculado que cambia un consentimiento, entonces se envía `PUT …/consentimientos/{tipo}` con su versión.
19. Dado un cliente vinculado que revoca la integración, entonces se cancelan las actualizaciones pendientes, se envían los consentimientos ya encolados y luego `DELETE …/autorizaciones/{id}`; la referencia se conserva.
20. Dado un cliente vinculado, cuando cambia su teléfono en «Mi perfil», entonces se encola una actualización (agrupada si ya había una) con `datos_al`; el nombre visible no se notifica.
21. Dado un 409 de HCVet en la actualización, entonces la operación queda `conflicto` y el vínculo sigue `vinculado`.
22. Dado un cliente vinculado, cuando intenta cambiar su DNI en «Mi perfil», entonces 409 `DNI_LOCKED_BY_HCVET`.
23. Dado un admin, cuando lista la cola, entonces ve estados y errores sin DNI ni correos; un cliente recibe 403.

## Criterios de aceptación

- Escenarios 1–23 (con 10b y 10c) cubiertos por `tests/unit/test_integracion_hcvet.py` (HCVet simulado; sin
  credenciales reales). En HCVet, D-105 cubierto por sus pruebas de alta, autorizaciones y seguridad.
- Migraciones `f4b2c8e1a7d3` (Paku) y `e5a9c3f7d2b4` (HCVet) generan SQL de subida y bajada; **no aplicadas**.
- paku-web y paku-vet-dev muestran la sección de consentimientos y el estado; lógica compartida probada.
