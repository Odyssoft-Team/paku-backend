# PAKU + HCVET — Tareas: bloque A (propietarios, identidad y autorización)

Plan de referencia: [PAKU-HCVET-IMPLEMENTATION-PLAN.md](PAKU-HCVET-IMPLEMENTATION-PLAN.md).
Requerimientos: [PAKU-HCVET-REQUIREMENTS.md](PAKU-HCVET-REQUIREMENTS.md).

Estados: `Pendiente` · `En progreso` · `Completada` · `Bloqueada`.
Una tarea solo pasa a `Completada` con implementación, criterios y pruebas cumplidos.
Repositorio de todas estas tareas: `hcvet-backend`. Ninguna tarea hace commit, push ni cambios en producción sin autorización.

## Orden de ejecución y resumen

| Orden | ID | Tarea | Depende de | Prioridad | Estado |
|---|---|---|---|---|---|
| 1 | HCV-001 | Cerrar decisiones Q1–Q8 | — | Alta | Completada |
| 2 | HCV-002 | Spec 0005: identidad y autorización delegada | HCV-001 | Alta | Completada |
| 3 | HCV-004 | Tipo de plataforma y control de claves de API | HCV-002 | Alta | Completada |
| 4 | HCV-010 | Auditoría (tabla de solo inserción) | HCV-002 | Alta | Completada |
| 5 | HCV-003 | Cuenta opcional para el propietario | HCV-002 | Alta | Completada |
| 6 | HCV-005 | Autorizaciones delegadas y catálogo de alcances | HCV-003, HCV-004, HCV-010 | Alta | Completada |
| 7 | HCV-006 | Actor de plataforma delegada y autorización por alcance | HCV-005 | Alta | Completada |
| 8 | HCV-007 | Consentimientos por finalidad | HCV-003, HCV-010 | Media | Completada |
| 9 | HCV-008 | Registro idempotente y vinculación de propietarios | HCV-006, HCV-007, fase 2 (0002) | Alta | Completada |
| 10 | HCV-009 | Actualización controlada de datos básicos | HCV-006, HCV-010 | Media | Completada |
| 11 | HCV-011 | Límite de peticiones por plataforma (antes: por clave) | HCV-004 | Media | Completada |
| 12 | HCV-012 | Pruebas de seguridad del bloque | HCV-005 a HCV-011 | Alta | Completada |
| 13 | HCV-013 | Documentación SDD y de integración | HCV-012 | Media | Completada |

Ejecutables en paralelo: HCV-004 y HCV-010 (después de HCV-002); HCV-003 y HCV-004 (ambas después de HCV-002); HCV-007 y HCV-009 (después de sus dependencias).

---

## HCV-001 · Cerrar decisiones Q1–Q8

- **Repositorio:** hcvet-backend (registro en `DECISIONS.md`).
- **Módulo:** documentación.
- **Objetivo:** tener respuestas registradas para las preguntas que cambian arquitectura, seguridad o reglas de negocio.
- **Alcance:** Q1 (cuenta opcional), Q2 (indexación frente a autorización), Q3 (verificación de titularidad), Q4 (quién registra el consentimiento), Q5 (catálogo de alcances), Q6 (tabla `centros` con tipo), Q7 (DNI ya existente), Q8 (efecto de revocar). Cada una con la respuesta del usuario o, si la acepta, la recomendación.
- **Dependencias:** ninguna.
- **Prioridad:** alta.
- **Archivos:** [plan §7](PAKU-HCVET-IMPLEMENTATION-PLAN.md). Registro en `DECISIONS.md` pendiente de HCV-013 (ver nota de cierre).
- **Criterios de aceptación:**
  - Ocho decisiones con su origen (`*(Usuario)*` o `*(Propuesto por Claude, aceptado)*`).
  - Las decisiones que reemplazan D-048, D-049, D-066 o D-067 indican cuáles reemplazan.
  - Ninguna decisión queda en "pendiente de confirmar".
- **Pruebas requeridas:** no aplica.
- **Estado:** Completada (2026-11-27).
- **Nota de cierre:** Q1 a Q8 aprobadas y registradas en el plan §7; Q5 con precisiones (2026-11-27). La constitución pide registrar las decisiones también en `DECISIONS.md`: esa entrada se hace en HCV-013 junto con la aprobación de la spec 0005, para no tocar la base de decisiones antes de cerrar el spec.
- **Riesgos:** si Q2 se decide como "indexación = acceso", R9 y R10 no se pueden cumplir como exige REQUIREMENTS §5.2.
- **Referencia spec:** no aplica.

## HCV-002 · Spec 0005: identidad y autorización delegada

- **Repositorio:** hcvet-backend.
- **Módulo:** specs (`specs/features/0005-identidad-y-autorizacion-delegada/`).
- **Objetivo:** un spec aprobado que cubra HCV-003 a HCV-010, con sus reglas de negocio citadas.
- **Alcance:** `spec.md`, `plan.md` y `tasks.md` siguiendo `specs/README.md`. No incluye código.
- **Dependencias:** HCV-001.
- **Prioridad:** alta.
- **Archivos:** `specs/features/0005-identidad-y-autorizacion-delegada/*`, `specs/features/README.md`.
- **Criterios de aceptación:**
  - Estado `approved` en el spec después de la aprobación del usuario.
  - Cada comportamiento usa la forma **Dado / cuando / entonces** y cita `DOMAIN.md`.
  - Las preguntas abiertas que queden están marcadas como bloqueantes o no bloqueantes.
- **Pruebas requeridas:** no aplica.
- **Estado:** Completada (2026-11-27). Spec 0005 aprobado; decisiones D-084 a D-097 en `DECISIONS.md`.
- **Riesgos:** un spec demasiado grande; dividir si supera lo que el usuario puede revisar en una sesión.
- **Referencia spec:** esta tarea crea la referencia para HCV-003 a HCV-010.

## HCV-003 · Cuenta opcional para el propietario

- **Repositorio:** hcvet-backend.
- **Módulo:** `propietarios`, `cuentas`.
- **Objetivo:** un propietario puede existir sin cuenta ni contraseña (R1, R2).
- **Alcance:**
  - Migración nueva: `propietarios.cuenta_id` pasa a nulo; `propietarios.email` se agrega, obligatorio cuando no hay cuenta (CHECK).
  - `PropietarioLeido.email` toma el dato de la cuenta cuando existe, o de la columna en otro caso.
  - El correo no se cambia desde una plataforma si el propietario tiene cuenta (plan §4.8).
  - La activación con cuenta (`POST /v1/cuentas/activacion`) sigue igual.
  - No se crea todavía el alta por plataforma (eso es HCV-008).
- **Dependencias:** HCV-002 y la decisión Q1 (HCV-001).
- **Prioridad:** alta.
- **Archivos:** `src/hcvet/modulos/propietarios/modelos.py`, `esquemas.py`, `servicio.py`; `src/hcvet/modulos/cuentas/servicio.py`; `alembic/versions/<nueva>.py`; `tests/propietarios/`, `tests/cuentas/`.
- **Criterios de aceptación:**
  - Un propietario se puede construir sin cuenta en el servicio, con email propio.
  - Un propietario sin cuenta y sin email no puede guardarse (CHECK en BD y validación en esquema).
  - Las 195 pruebas actuales siguen en verde.
  - `alembic upgrade b3d9e4f1a2c7:head --sql` (o la revisión anterior vigente) se genera sin conexión y coincide con el DDL de los modelos.
- **Pruebas requeridas:** pruebas de servicio con sesión simulada; regresión completa; verificación offline de la migración.
- **Estado:** Completada (2026-11-27).
- **Resultado:** `propietarios.cuenta_id` admite nulos; nueva columna `propietarios.email` (atributo `email_contacto`) solo para propietarios sin cuenta; CHECK `ck_propietarios_cuenta_o_email` exige exactamente uno de los dos, así el correo nunca se duplica. La propiedad `Propietario.email` devuelve el de la cuenta o el de contacto, y `PropietarioLeido` no cambia de forma. Nuevo esquema `PropietarioSinCuentaCrear` (correo obligatorio, consentimientos sin valor por defecto) y función pura `propietarios.servicio.nuevo_sin_cuenta`, que usará HCV-008. `Email` pasó a `hcvet/tipos.py` para evitar un import circular; `cuentas.esquemas` lo reexporta. La activación con cuenta no cambia. Migración `f2a5c9e3b7d1` (sobre `e1f4b8d2a6c3`), sin ejecutar; su downgrade falla a propósito si ya hay propietarios sin cuenta.
- **Verificación:** `uv run pytest` 231 en verde (7 nuevas en `tests/propietarios/test_sin_cuenta.py` y una comprobación añadida a la activación). Migración offline (upgrade y downgrade) sin errores, una sola cabeza, DDL igual al modelo.
- **Pendiente para otras tareas:** el cambio de correo por una plataforma (D-093) se implementa en HCV-009; un propietario sin cuenta no puede iniciar sesión, porque no tiene credenciales.
- **Riesgos:** `Propietario.email` es hoy una propiedad (D-051). Cambiar su origen puede afectar la respuesta de `GET /v1/propietarios/{dni}`. Verificar con los contratos de `docs/INTEGRACION.md`.
- **Referencia spec:** 0005 (pendiente de HCV-002).

## HCV-004 · Tipo de plataforma y control de claves de API

- **Repositorio:** hcvet-backend.
- **Módulo:** `centros` (se mantiene el nombre de tabla, decisión Q6), `acceso`.
- **Objetivo:** identificar la plataforma y controlar el uso de cada clave (R7, R8, R16).
- **Alcance:**
  - `centros.tipo`: `plataforma` o `establecimiento`. Valor por defecto `establecimiento` para no cambiar los centros existentes.
  - `claves_api.ultimo_uso_en` (nulo al inicio), actualizado al autenticar con escritura limitada (no más de una vez por hora por clave).
  - `claves_api.expira_en` opcional: una clave vencida responde 401 igual que una revocada.
  - `centro_por_clave` rechaza claves vencidas.
- **Dependencias:** HCV-002.
- **Prioridad:** alta.
- **Archivos:** `src/hcvet/modulos/centros/modelos.py`, `servicio.py`, `esquemas.py`, `rutas.py`; `src/hcvet/modulos/acceso/dependencias.py`; migración nueva; `tests/centros/`, `tests/acceso/`, `tests/test_api.py`.
- **Criterios de aceptación:**
  - Clave revocada → 401 (comportamiento actual, sin cambio).
  - Clave vencida → 401 con el mensaje de clave inválida.
  - Autenticar con una clave actualiza `ultimo_uso_en` como máximo una vez por hora.
  - `GET /v1/centros/actual` sigue devolviendo solo nombre comercial, razón social y RUC.
  - Las claves existentes siguen válidas tras la migración.
- **Pruebas requeridas:** pruebas de servicio (vencida, revocada, vigente, escritura limitada); pruebas HTTP con 401.
- **Estado:** Completada (2026-11-27).
- **Resultado:** `TipoCentro` (`establecimiento` por defecto, `plataforma`) en `centros.tipo`, aceptado en el alta y devuelto en `CentroLeido`. `claves_api.expira_en` (opcional; se fija con el cuerpo opcional `{"expira_en"}` de `POST /v1/administracion/centros/{id}/claves`, debe ser futuro y con zona horaria) y `claves_api.ultimo_uso_en`. `centro_por_clave` rechaza claves vencidas (401 como una revocada) y registra el último uso como máximo una vez por hora. Auditoría reutilizada (HCV-010): el alta registra el tipo y la emisión indica si tiene vencimiento; el último uso no se audita. `GET /v1/centros/actual` sin cambios. Migración `e1f4b8d2a6c3` (sobre `d7e3a9c5b2f1`), sin ejecutar.
- **Verificación:** `uv run pytest` 224 en verde (15 nuevas en `tests/centros/test_claves.py` y `tests/centros/test_rutas_claves.py`). Migración offline (upgrade y downgrade) sin errores, una sola cabeza, DDL igual al modelo.
- **Riesgos:** escribir `ultimo_uso_en` en cada petición carga la BD. Por eso se limita la escritura.
- **Referencia spec:** 0005.

## HCV-005 · Autorizaciones delegadas y catálogo de alcances

- **Repositorio:** hcvet-backend.
- **Módulo:** nuevo `autorizaciones` (en `src/hcvet/modulos/autorizaciones/`).
- **Objetivo:** que una plataforma actúe en nombre de un propietario solo con una autorización vigente, sin contraseñas (R9, R10).
- **Alcance:**
  - Tablas `autorizaciones` (plataforma, propietario, estado, `otorgada_en`, `revocada_en`, `version_terminos`, `origen`) y `autorizacion_alcances` (catálogo de §4.4 del plan).
  - Unicidad: una autorización vigente por par (plataforma, propietario).
  - Los alcances se eligen explícitamente al otorgar; no existe una autorización con todos los alcances por defecto (Q5, plan §4.3 regla 5).
  - `evento.corregir` se limita a los eventos registrados por la misma plataforma. Los eventos ajenos no se corrigen (D-097).
  - Servicio: otorgar, listar por propietario, revocar. La revocación no borra filas (Q8).
  - Rutas: `POST /v1/propietarios/{dni}/autorizaciones`, `GET …/autorizaciones`, `DELETE …/autorizaciones/{id}`.
  - Cada operación registra auditoría (HCV-010).
- **Dependencias:** HCV-003, HCV-004, HCV-010; decisiones Q3, Q5, Q8.
- **Prioridad:** alta.
- **Archivos:** `src/hcvet/modulos/autorizaciones/{modelos,esquemas,repositorio,servicio,rutas}.py`; `src/hcvet/main.py`; `alembic/versions/<nueva>.py`; `tests/autorizaciones/`.
- **Criterios de aceptación:**
  - Otorgar una autorización a un propietario existente → 201.
  - Otorgar una segunda vigente para el mismo par → 409.
  - Revocar → 204; revocar de nuevo → 204 sin cambios (idempotente).
  - Un alcance fuera del catálogo → 422 sin devolver el valor recibido (D-058).
  - Listar no muestra autorizaciones de otros propietarios.
  - Una autorización revocada no aparece como vigente.
- **Pruebas requeridas:** pruebas de servicio; pruebas HTTP de los tres endpoints (401 sin clave, 403 con sesión de administrador).
- **Estado:** Completada (2026-11-28).
- **Resultado:** módulo `src/hcvet/modulos/autorizaciones/` con tablas `autorizaciones` y `autorizacion_alcances` (catálogo `Alcance`, D-088). Una sola autorización vigente por par (índice único parcial; la carrera se traduce a 409). Alcances obligatorios, sin repetidos y sin valor por defecto. Rutas `POST`, `GET` y `DELETE` en `/v1/propietarios/{dni}/autorizaciones`:
  - El dueño (sesión) otorga a un centro existente (`centro_id`), sin evidencia.
  - La plataforma (API Key) solo se otorga a sí misma y debe presentar evidencia de titularidad (método, fecha y referencia; D-086), guardada en la autorización. Sin evidencia → 422. *(Rectificado el 2026-11-28 por D-105: sin evidencia; la vinculación de una plataforma es de acceso básico.)*
  - Listar: el dueño ve todas; la plataforma solo las propias y, si no tiene ninguna, recibe el mismo 404 que un DNI inexistente (D-090).
  - Revocar: guarda fecha y quién revocó; no borra (D-091); revocar de nuevo no cambia nada (204).
  - El administrador recibe 403. Cada otorgamiento y revocación queda auditado (HCV-010).
  - Nuevo error de dominio `DatosInvalidos` → 422.
  - `Autorizacion.permite(alcance)` es la comprobación que usará HCV-006.
  - Migración `a8c4e2f6b9d3` (sobre `f2a5c9e3b7d1`), sin ejecutar.
- **Compatibilidad:** las rutas existentes (propietarios, mascotas, pesos, eventos) no cambian todavía: siguen con la regla de indexación. La restricción por alcance sobre ellas, con autorizaciones de transición para las integraciones actuales, es HCV-006. Hasta entonces, una API Key conserva el acceso de la fase 1.
- **Verificación:** `uv run pytest` 263 en verde (32 nuevas en `tests/autorizaciones/`). Migración offline (upgrade y downgrade) sin errores, una sola cabeza, DDL igual al modelo.
- **Riesgos:** el catálogo de alcances crece fácilmente; mantenerlo cerrado (Q5). Q3 determina quién puede otorgar.
- **Referencia spec:** 0005.

## HCV-006 · Actor de plataforma delegada y autorización por alcance

- **Repositorio:** hcvet-backend.
- **Módulo:** `acceso`, `propietarios`, `mascotas` (solo las rutas de este bloque).
- **Objetivo:** que las rutas de propietario comprueben la autorización vigente y su alcance, en lugar de solo la indexación (R4, R10, R11; decisión Q2).
- **Alcance:**
  - `ActorPlataformaDelegada(plataforma, propietario, alcances)`, resuelto cuando la petición trae API Key y un DNI en la ruta.
  - Rutas de propietario (`GET /v1/propietarios/{dni}`) exigen `propietario.consultar`.
  - Los actores existentes (`ActorCentro`, `ActorPropietario`) no cambian para las rutas que no se migran en este bloque.
  - Transición según Q2: si la decisión es (a), la indexación solo permite encontrar al dueño y el acceso exige autorización. Las plataformas que ya acceden reciben autorizaciones con los alcances actuales antes de la restricción.
- **Dependencias:** HCV-005; decisión Q2.
- **Prioridad:** alta.
- **Archivos:** `src/hcvet/modulos/acceso/{actores,dependencias,reglas}.py`; `src/hcvet/modulos/propietarios/{servicio,rutas}.py`; `src/hcvet/modulos/mascotas/servicio.py` (solo `crear`); `tests/acceso/`, `tests/propietarios/`, `tests/mascotas/`.
- **Criterios de aceptación:**
  - Plataforma sin autorización sobre un propietario → 404 (lectura), igual que un DNI inexistente.
  - Plataforma con autorización y alcance → 200.
  - Autorización revocada → 404 en la siguiente petición.
  - Alcance insuficiente para una escritura → 403.
  - Dueño propio sigue accediendo a sus datos.
  - Las pruebas de regla de visibilidad actuales pasan, salvo las que cambian por decisión Q2, que se actualizan y se documentan.
- **Pruebas requeridas:** pruebas de `acceso/reglas.py` (funciones puras); pruebas HTTP de cada caso; pruebas de transición (plataforma con indexación pero sin autorización).
- **Estado:** Completada (2026-11-28).
- **Resultado:**
  - `acceso/reglas.py` (funciones puras): `acceso_a_propietario` y `acceso_a_mascota` devuelven `PERMITIDO`, `NO_VISIBLE` (404) o `SIN_ALCANCE` (403). Un dueño opera lo suyo como antes. Una plataforma necesita autorización vigente con el alcance. La indexación solo sirve para `propietario_encontrable` (D-085).
  - `acceso/permisos.py`: `cargar` lee los alcances vigentes en una consulta por petición, limitada a los propietarios involucrados y sin caché, así la revocación tiene efecto inmediato. `exigir` traduce a 404 o 403.
  - Alcances por ruta:
    - `GET /propietarios/{dni}`: `propietario.consultar`.
    - `POST /mascotas`: `mascota.registrar` sobre el dueño principal.
    - `GET /mascotas/{id}`: `mascota.consultar`.
    - `GET` de pesos y eventos: `historial.consultar`.
    - `POST` de pesos y eventos: `evento.registrar`.
    - Mascota compartida: basta un propietario que conceda el alcance.
    - Copropietarios visibles: solo los que conceden `propietario.consultar`.
  - Búsqueda por DNI (`GET /propietarios/{dni}/mascotas`): sin autorización vigente responde **404** igual que un DNI inexistente, esté o no indexado (D-098, ajustado el 2026-11-28). Con autorización exige `propietario.consultar` y `mascota.consultar`; si falta uno, 403.
  - Ficha y vínculos de la mascota siguen siendo solo del dueño (`mascota.actualizar` no se aplica todavía: no se amplió el acceso en una tarea de restricción).
  - Transición: origen `transicion` y comando manual `python -m hcvet.modulos.autorizaciones.transicion --centro N --admin M [--aplicar]` (simula por defecto). Solo autoriza a dueños con indexación activa y con eventos o pesos ya registrados por esa plataforma, con cuatro alcances (`propietario.consultar`, `mascota.consultar`, `historial.consultar`, `evento.registrar`). Idempotente y auditado. La migración `a8c4e2f6b9d3` (sin ejecutar ni commitear) se editó para aceptar el origen `transicion`.
- **Verificación:** `uv run pytest` 313 en verde (50 nuevas o reescritas: matriz de reglas, carga de permisos y revocación, rutas por HTTP con 404/403/200 y acceso entre propietarios, consulta por DNI, transición). Migración offline sin errores, una sola cabeza.
- **Ajustes aprobados (2026-11-28):** búsqueda por DNI sin autorización → 404 (D-098). Transición condicionada a consentimiento previo suficiente; los dudosos (solo copropietario) no se autorizan y se listan para revisión manual; los que revocaron historial compartido o registro de eventos se excluyen (D-099). Definición de apto y dudoso pendiente de confirmar.
- **Despliegue:** con el código nuevo, una plataforma pierde acceso hasta tener autorizaciones. Orden sugerido: migraciones, transición en simulación, revisión, `--aplicar`, y luego tráfico. La consola de pruebas (`hcvet-dev-frontend`) no tiene todavía pantalla para otorgar autorizaciones.
- **Riesgos:** regresión en la fase 1 cerrada. Mitigación: autorizaciones de transición antes de restringir.
- **Referencia spec:** 0005.

## HCV-007 · Consentimientos por finalidad

- **Repositorio:** hcvet-backend.
- **Módulo:** nuevo `consentimientos`; `propietarios` (proyección de compatibilidad).
- **Objetivo:** registrar consentimientos por finalidad con fecha, origen y versión (R12, R13, R14).
- **Alcance:**
  - Tabla `consentimientos` (historial, solo inserción): `propietario_id`, `tipo`, `concedido`, `finalidad`, `version_texto`, `origen`, `registrado_en`.
  - Tipos: `indexacion_veterinaria`, `uso_comercial`, `historial_compartido`, `registro_eventos` (propuesta; confirmar en HCV-001).
  - Migración: cada booleano actual se convierte en una fila con `origen = migracion` y `version_texto = desconocida`. No se inventan fechas: `registrado_en` es la fecha de activación del propietario.
  - `GET /v1/propietarios/{dni}/consentimientos` y `PUT /v1/propietarios/{dni}/consentimientos/{tipo}`.
  - Los booleanos de `propietarios` se actualizan en la misma transacción, como proyección.
  - `permite_uso_comercial` se puede registrar; no tiene efecto (DOMAIN, Sin definir).
- **Dependencias:** HCV-003, HCV-010; decisión Q4.
- **Prioridad:** media.
- **Archivos:** `src/hcvet/modulos/consentimientos/*`; `src/hcvet/modulos/propietarios/servicio.py`; `alembic/versions/<nueva>.py`; `tests/consentimientos/`.
- **Criterios de aceptación:**
  - Ningún consentimiento tiene valor por defecto: `PUT` sin `concedido` → 422.
  - Cada cambio crea una fila nueva; el estado actual es la última fila por tipo.
  - La migración convierte los dos booleanos sin inventar fechas ni versiones.
  - La revocación de indexación sigue teniendo efecto inmediato en las búsquedas.
  - Un consentimiento sin versión de texto es rechazado.
- **Pruebas requeridas:** pruebas de servicio; prueba de la migración de datos (verificación offline y prueba con datos simulados); regresión de `PATCH …/permisos`.
- **Estado:** Completada (2026-11-28).
- **Resultado:** módulo `src/hcvet/modulos/consentimientos/`. Tabla `consentimientos` de solo inserción (`tipo`, `concedido`, `finalidad`, `version_texto`, `origen`, `registrado_en`); el estado actual es la última fila por tipo. `GET /v1/propietarios/{dni}/consentimientos` (dueño, o plataforma con `propietario.consultar`) y `PUT …/consentimientos/{tipo}` (dueño, o plataforma vinculada que comunica la decisión del dueño; D-087, D-094). Decisión y versión obligatorias, sin valor por defecto. Los booleanos de `propietarios` se actualizan en la misma transacción como proyección; la activación de cuenta y `PATCH /permisos` también dejan fila (versión `no_informada`). Una revocación explícita de `historial_compartido` o `registro_eventos` bloquea en la siguiente petición `historial.consultar` o `evento.registrar`; uso comercial se registra sin efecto. Auditado. Migración `b9d5f3a7c2e8` con migración de datos (origen `migracion`, versión `desconocida`, fecha de alta), sin ejecutar.
- **Verificación:** `uv run pytest` 349 en verde (29 nuevas en `tests/consentimientos/`, incluida la migración de datos con `op` simulado). Migración offline sin errores, una sola cabeza, DDL igual al modelo.
- **Pendiente de confirmar:** tipos de consentimiento y su efecto sobre los alcances (D-100). Texto legal de cada finalidad, antes de producción.
- **Riesgos:** duplicar la fuente de verdad entre booleanos y tabla. Mitigación: la proyección se escribe solo desde el servicio de consentimientos.
- **Referencia spec:** 0005.

## HCV-008 · Registro idempotente y vinculación de propietarios

- **Repositorio:** hcvet-backend.
- **Módulo:** `propietarios`, `identidad`.
- **Objetivo:** que una plataforma autorizada registre o vincule un propietario sin duplicarlo y sin contraseñas (R2, R3, R5).
- **Alcance:**
  - `POST /v1/propietarios` con alcance `propietario.registrar`. Crea el propietario sin cuenta, con sus consentimientos y su autorización inicial.
  - DNI nuevo → 201. DNI existente con autorización vigente de la misma plataforma → 200 con el propietario existente (sin revelar datos nuevos). DNI existente sin autorización → 409 con el mensaje de vinculación (Q7).
  - Vinculación verificada según Q3. Si Q3 es (a), la plataforma certifica la titularidad y HCVet guarda el nivel de confianza y la plataforma que lo certificó.
  - Traducir la violación de `UNIQUE(dni)` en la carrera a 409, no a 500.
  - La clave de idempotencia se añade cuando esté lista la fase 2 (0002); hasta entonces, el alta solo es idempotente por el DNI.
- **Dependencias:** HCV-006, HCV-007, HCV-005; fase 2 (0002) para cerrar la idempotencia; decisiones Q3 y Q7.
- **Prioridad:** alta.
- **Archivos:** `src/hcvet/modulos/propietarios/{esquemas,servicio,rutas,repositorio}.py`; `src/hcvet/modulos/identidad/servicio.py` (solo si Q3 usa proveedor); `tests/propietarios/`.
- **Criterios de aceptación:**
  - Alta sin cuenta ni contraseña → 201; el propietario tiene consentimientos y autorización.
  - Mismo DNI y misma plataforma → 200; no se crea un segundo propietario.
  - Mismo DNI sin autorización → 409; la respuesta no incluye nombres ni email del propietario existente.
  - Dos altas concurrentes con el mismo DNI (simuladas) → una 201 y una 409 o 200, nunca 500.
  - Sin alcance `propietario.registrar` → 403.
- **Pruebas requeridas:** pruebas de servicio con sesión simulada; pruebas de la traducción de la violación de restricción; pruebas HTTP (401, 403, 409, 422).
- **Estado:** Completada (2026-11-28).
- **Resultado:**
  - `POST /v1/propietarios` (solo plataformas; una persona recibe 403 y usa `/v1/cuentas`). En una transacción crea el propietario sin cuenta (HCV-003), su autorización inicial de origen `plataforma` (debe incluir `propietario.registrar`, con evidencia de titularidad), los consentimientos de indexación y uso comercial y los explícitos de historial compartido y registro de eventos, y la auditoría (`propietario.alta`, `autorizacion.otorgamiento`).
  - DNI nuevo → 201. DNI ya registrado por la misma plataforma con autorización vigente → 200 con los mismos identificadores, sin duplicar. DNI existente sin autorización → 409 sin datos personales, con la indicación de vincular con evidencia en `POST /v1/propietarios/{dni}/autorizaciones` (D-086, D-090). Alta concurrente del mismo DNI → 409, nunca 500. La respuesta solo lleva identificadores.
  - Idempotencia adelantada de la feature 0002 (D-102), solo para esta ruta: módulo `idempotencia`, tabla `solicitudes_idempotentes`, cabecera `Idempotency-Key` (1 a 255), ventana de 24 h, claves por credencial, misma clave y cuerpo → misma respuesta sin repetir la operación, otro cuerpo → 409, violación de restricción al confirmar → 409.
  - Precisiones de D-101 aplicadas: en integraciones nuevas, un alcance dependiente de un consentimiento exige que esté concedido; la transición solo autoriza con evidencia del consentimiento anterior (sin ella, dudoso).
  - Migración `c1e7a4d9f3b6` (sobre `b9d5f3a7c2e8`), sin ejecutar.
- **Verificación:** `uv run pytest` 385 en verde (28 nuevas: idempotencia, alta por plataforma y HTTP con `Idempotency-Key`; otras reescritas por D-101). Migración offline sin errores, una sola cabeza, DDL igual al modelo.
- **Riesgo abierto:** el 409 de un DNI existente revela que existe (aprobado en Q7); las consultas abusivas se contienen con HCV-011 (límite por clave), todavía pendiente.
- **Riesgos:** alta sin titularidad (R5). Mitigación: Q3 y auditoría. Carreras: mitigación en el servicio y, al cerrar, con la clave de idempotencia de la fase 2.
- **Referencia spec:** 0005.

## HCV-009 · Actualización controlada de datos básicos

- **Repositorio:** hcvet-backend.
- **Módulo:** `propietarios`.
- **Objetivo:** actualizar nombres, apellidos, distrito y teléfono sin sobrescribir datos recientes ni verificados (R6).
- **Alcance:**
  - `PATCH /v1/propietarios/{dni}` con alcance `propietario.actualizar` o con sesión del propio dueño.
  - Campos: nombres, apellidos, distrito, teléfono y correo (Q5). El correo de un propietario con cuenta no se cambia sin confirmación del dueño (plan §4.8).
  - Columnas nuevas en `propietarios`: `actualizado_en`, `origen_actualizacion`, y el origen de la verificación cuando exista.
  - El DNI no se modifica.
  - Política: un dato verificado no se sobrescribe con uno no verificado de otra plataforma; el conflicto responde 409 sin revelar el valor anterior.
- **Dependencias:** HCV-006, HCV-010; decisión Q2 (acceso) y la política de conflictos (se propone en el plan §4.8).
- **Prioridad:** media.
- **Archivos:** `src/hcvet/modulos/propietarios/{esquemas,servicio,rutas,modelos}.py`; `alembic/versions/<nueva>.py`; `tests/propietarios/`.
- **Criterios de aceptación:**
  - Un campo básico válido se actualiza y registra `origen_actualizacion`.
  - Intentar cambiar el DNI → 422.
  - Cambiar el correo de un propietario con cuenta desde una plataforma → 409 o 403, según la spec 0005, sin modificar `cuentas.email`.
  - Un dato verificado no se sobrescribe desde otra plataforma → 409.
  - Sin alcance `propietario.actualizar` → 403.
  - Una actualización deja una fila de auditoría.
- **Pruebas requeridas:** pruebas de servicio; pruebas HTTP; prueba de la política de conflicto.
- **Estado:** Completada (2026-11-28).
- **Cambio respecto del alcance original:** la procedencia se guarda **por campo** en la tabla `propietario_campos` (no en columnas únicas de `propietarios`), para saber de cada dato su fuente, autor, fecha y verificación (D-104).
- **Resultado:** `PATCH /v1/propietarios/{dni}`.
  - **Permisos:** el propio dueño, o una plataforma con `propietario.actualizar`. Sin relación, 404; sin el alcance, 403. El DNI no se acepta (422, sin repetir el valor). Solo las plataformas informan verificaciones.
  - **Correo:** con cuenta, es la credencial de acceso y no se cambia por esta vía (409, `cuentas.email` intacto); sin cuenta, es dato de contacto y se actualiza (D-093).
  - **Datos verificados:** solo se reemplazan con una verificación igual o más reciente (D-095); un valor nuevo sin verificación queda no verificado; se puede verificar el valor actual sin cambiarlo. La lectura del propietario incluye `verificados` (campo agregado, compatible).
  - **Datos desactualizados:** cada solicitud declara `datos_al`; un campo con fuente más reciente responde 409. Validación completa antes de aplicar (atómica) y bloqueo `FOR UPDATE` de la fila durante la actualización.
  - **Procedencia y auditoría:** por campo, fuente (`fuente_en`), autor (`actualizado_por`) y fecha; auditoría `propietario.actualizacion` con los nombres de los campos, sin valores. Sin cambios efectivos, no se audita ni confirma.
  - Migración `d4f8b2e6a1c9` (sobre `c1e7a4d9f3b6`), sin ejecutar.
- **Verificación:** `uv run pytest` 432 en verde (28 nuevas en `tests/propietarios/test_actualizacion.py`), estable en 6 ejecuciones. Migración offline sin errores, una sola cabeza, DDL igual al modelo. Nota: con `HCVET_DATABASE_URL` definida en el entorno fallan 3 pruebas previas de `tests/test_config.py` (dependen de que no esté definida); no es un efecto de esta tarea.
- **Pendiente:** flujo de cambio del correo de acceso con confirmación del dueño (fuera de este bloque). Propuestas de D-104 por confirmar.
- **Riesgos:** la política de conflictos es una decisión de negocio que debe quedar en DOMAIN antes de implementarse.
- **Referencia spec:** 0005.

## HCV-010 · Auditoría de solo inserción

- **Repositorio:** hcvet-backend.
- **Módulo:** nuevo `auditoria`.
- **Objetivo:** registrar quién hizo qué sobre propietarios, consentimientos, claves y autorizaciones (R15, R18).
- **Alcance:**
  - Tabla `auditoria`: `ocurrido_en`, `actor` (`plataforma:{id}`, `propietario:{id}` o `administrador`; nunca DNI ni email), `accion`, `entidad`, `entidad_id`, `resumen` (sin valores personales).
  - Servicio `registrar(sesion, actor, accion, entidad, entidad_id, resumen)`, llamado desde el servicio y en la misma transacción.
  - Sin rutas de lectura en esta tarea; la consulta de auditoría se decide aparte.
- **Dependencias:** HCV-002.
- **Prioridad:** alta (HCV-005, HCV-007, HCV-008 y HCV-009 la necesitan).
- **Archivos:** `src/hcvet/modulos/auditoria/*`; `alembic/versions/<nueva>.py`; `tests/auditoria/`.
- **Criterios de aceptación:**
  - Cada acción registrada crea exactamente una fila en la misma transacción.
  - Si la acción falla, no queda fila de auditoría.
  - La tabla no tiene rutas de modificación ni de borrado.
  - Ningún registro contiene DNI ni email completos.
- **Pruebas requeridas:** pruebas de servicio; prueba de atomicidad con sesión simulada; prueba de contenido (sin DNI ni email).
- **Estado:** Completada (2026-11-27).
- **Resultado:** módulo `src/hcvet/modulos/auditoria/` (modelo `RegistroAuditoria`, repositorio, servicio `registrar`), sin rutas. La columna de fecha es `creado_en` (D-040) en lugar de `ocurrido_en`. El actor solo acepta `administrador|centro|propietario:<id>`; el resumen rechaza DNI y correos. Conectada a alta de centro, emisión y revocación de claves (actor `administrador:<id>`) y cambio de indexación (actor `propietario:<id>`). Migración `d7e3a9c5b2f1` (sobre `c4a8e2f1d9b0`), sin ejecutar.
- **Verificación:** `uv run pytest` 209 en verde (14 pruebas nuevas en `tests/auditoria/`). `alembic upgrade c4a8e2f1d9b0:head --sql` y su downgrade sin errores; el DDL coincide con el modelo.
- **Riesgos:** volumen de la tabla; definir retención en HCV-013.
- **Referencia spec:** 0005.

## HCV-011 · Límite de peticiones por clave de API

- **Repositorio:** hcvet-backend.
- **Módulo:** `acceso`.
- **Objetivo:** limitar el consumo de cada plataforma (R17).
- **Alcance:**
  - Límite por clave (ventana deslizante en memoria, sin dependencias nuevas).
  - Configurable con `HCVET_LIMITE_PETICIONES_POR_MINUTO`.
  - Responde 429 con `Retry-After`.
  - Documentar la limitación: el contador es por proceso; con varias instancias hay que cambiar a un almacén compartido.
- **Dependencias:** HCV-004.
- **Prioridad:** media.
- **Archivos:** `src/hcvet/modulos/acceso/limite.py` (nuevo), `src/hcvet/config.py`, `src/hcvet/main.py`, `tests/acceso/`.
- **Criterios de aceptación:**
  - Superar el límite por clave → 429; otra clave no se ve afectada.
  - La ventana se reinicia con el tiempo.
  - El límite es configurable y tiene un valor por defecto documentado.
- **Pruebas requeridas:** pruebas unitarias del contador con reloj simulado; prueba HTTP de 429.
- **Estado:** Completada (2026-11-28).
- **Cambio respecto del alcance original:** se cuenta **por plataforma** y no por clave, para que la rotación de claves no permita eludir el límite (pedido del usuario; D-103).
- **Resultado:** `src/hcvet/modulos/acceso/limite.py` (sin dependencias nuevas). Tres reglas configurables, comprobadas y registradas de forma atómica bajo un lock (una petición rechazada no consume nada): peticiones por minuto (`HCVET_LIMITE_PETICIONES_POR_MINUTO`, 600), peticiones por minuto a rutas con DNI (`HCVET_LIMITE_CONSULTAS_DNI_POR_MINUTO`, 120; incluye `POST /v1/propietarios`) y DNI distintos por hora (`HCVET_LIMITE_DNI_DISTINTOS_POR_HORA`, 1000; repetir un DNI no suma). Se aplica al resolver la credencial de una plataforma (`obtener_actor`); las personas con sesión no se limitan por esta vía. Al superar: 429 con `Retry-After` y `reintentar_en`. Valores por defecto holgados para no afectar a las integraciones existentes. Variables en `README.md` y `.env.example`. Sin migración.
- **Verificación:** `uv run pytest` 404 en verde (19 nuevas en `tests/acceso/test_limite.py`: ventana deslizante, momento de reintento, DNI distintos, atomicidad, concurrencia con 20 hilos (estable en 5 ejecuciones), reglas por ruta y configuración; por HTTP: 429 con `Retry-After`, rotación de claves, plataformas independientes, ráfaga y búsqueda masiva de DNI, sesión no limitada). Además, la prueba de la distinción de D-102 (reintento con la misma clave frente a solicitud nueva).
- **Limitación:** el contador vive en memoria del proceso; con varias instancias o procesos de la API cada uno cuenta por separado. Valores por defecto pendientes de confirmar.
- **Riesgos:** plataformas detrás de una misma IP. Por eso el límite es por clave y no por IP.
- **Referencia spec:** 0005.

## HCV-012 · Pruebas de seguridad del bloque

- **Repositorio:** hcvet-backend.
- **Módulo:** `tests/` (transversal).
- **Objetivo:** cubrir los casos de seguridad del bloque (REQUIREMENTS §15, sección Autorización y Registro e identidad, en la parte que corresponde a HCVet).
- **Alcance:**
  - Clave válida, inválida, revocada y vencida.
  - Propietario autorizado y no autorizado.
  - Consentimiento revocado.
  - Plataforma con alcances insuficientes.
  - Acceso a mascotas de otro propietario por una plataforma autorizada a otro.
  - DNI ajeno en la vinculación.
  - Enumeración: respuestas idénticas para DNI inexistente y no visible.
- **Dependencias:** HCV-005 a HCV-011.
- **Prioridad:** alta.
- **Archivos:** `tests/seguridad/` (nuevo) o los módulos correspondientes.
- **Criterios de aceptación:**
  - Todos los casos listados están cubiertos por al menos una prueba.
  - `uv run pytest` en verde.
  - Ninguna prueba usa credenciales reales ni datos reales (constitución 25 y REQUIREMENTS §5.4).
- **Pruebas requeridas:** es la propia tarea.
- **Estado:** Completada (2026-11-28).
- **Resultado:** `tests/seguridad/test_bloque_a.py`, 21 pruebas por HTTP que reúnen todos los casos: clave vigente, inexistente, revocada y vencida; administrador sin acceso; propietario autorizado y no autorizado; alcance insuficiente; acceso horizontal a mascotas y entre dueños; consentimiento revocado (global, incluso en transición) y ausente en integraciones nuevas; vinculación sin evidencia y DNI ajeno; alta de un DNI existente sin revelar datos; enumeración (seis rutas responden igual a un DNI inexistente y a uno existente sin autorización); búsqueda masiva de DNI → 429. Ninguna usa credenciales ni datos reales.
- **Aislamiento corregido:** las pruebas ya no dependen de variables `HCVET_*` ni de un `.env` (fixture global en `tests/conftest.py`: limpia el entorno y la caché de configuración). Verificado con variables hostiles definidas.
- **Verificación:** `uv run pytest` 453 en verde, con y sin variables `HCVET_*` en el entorno.
- **Riesgos:** pruebas que solo verifican el código y no el comportamiento HTTP. Incluir pruebas con `TestClient`.
- **Referencia spec:** 0005.

## HCV-013 · Documentación SDD y de integración

- **Repositorio:** hcvet-backend.
- **Módulo:** documentación.
- **Objetivo:** dejar el arnés al día con el bloque implementado (constitución 30).
- **Alcance:**
  - `DOMAIN.md`: cuenta opcional, autorización por plataforma, alcances, consentimientos, reglas de vinculación.
  - `DECISIONS.md`: decisiones nuevas y reemplazos de D-048, D-049, D-066 o D-067 según HCV-001.
  - `ARCHITECTURE.md`: módulos `autorizaciones`, `consentimientos`, `auditoria` y el actor de plataforma.
  - `docs/INTEGRACION.md`: flujo para plataformas (alta, vinculación, autorización, consentimiento).
  - `STATUS.md` y `README.md`.
  - `specs/features/0005-…`: estado `done` solo si HCV-001 a HCV-012 están completadas.
- **Dependencias:** HCV-012.
- **Prioridad:** media.
- **Archivos:** los indicados.
- **Criterios de aceptación:**
  - Ninguna regla de DOMAIN contradice el código ni una decisión vigente.
  - Las contradicciones del plan §3.2 están resueltas o marcadas como pendientes.
  - Los ejemplos de `docs/INTEGRACION.md` se ejecutaron contra el código de pruebas.
- **Pruebas requeridas:** no aplica; revisión cruzada de documentos.
- **Estado:** Completada (2026-11-28).
- **Resultado:** actualizados `DOMAIN.md` (cuenta opcional, autorización delegada y alcances, consentimientos, vinculación, actualización con procedencia, límites; sin definir: textos legales, flujo de correo de acceso, confirmación de contactos), `DECISIONS.md` (D-084 a D-104), `ARCHITECTURE.md` (módulos `autorizaciones`, `consentimientos`, `auditoria`, `idempotencia`, `acceso/permisos` y `acceso/limite`; 16 tablas; migraciones), `docs/INTEGRACION.md` (flujo para plataformas: alta, vinculación, alcances, consentimientos, errores 403/404/409/429, idempotencia y límites), `README.md` (rutas, reglas, variables), `STATUS.md` y spec 0005.
- **Validación de migraciones:** la cadena completa `base → head` (10 migraciones) genera SQL de subida y bajada sin errores y crea exactamente las 16 tablas de los modelos. **Bloqueada** la validación contra un PostgreSQL de pruebas: no hay PostgreSQL ni Docker en la máquina, y la instalación de un PostgreSQL empaquetado desde PyPI (`pgserver`) fue rechazada por el control de permisos. El spec 0005 queda `in-progress` hasta esa validación.
- **Riesgos:** documentación que describe un estado futuro. Marcar lo no implementado.
- **Referencia spec:** 0005.

---

## HCV-014 · Validar las migraciones del bloque A en PostgreSQL de pruebas

- **Repositorio:** hcvet-backend.
- **Objetivo:** confirmar en un PostgreSQL real las ocho migraciones `c4a8e2f1d9b0` a `d4f8b2e6a1c9` antes de desplegar el bloque A.
- **Alcance:** subida desde la base vacía, migración de datos de consentimientos con filas de ejemplo, bajada y nueva subida, `alembic check` contra los modelos. Nunca sobre producción.
- **Dependencias:** HCV-013.
- **Prioridad:** alta. **Bloqueante para el despliegue del bloque A.**
- **Criterios de aceptación:** las cuatro operaciones sin errores; `alembic check` sin diferencias; los consentimientos migrados conservan fecha de alta, versión `desconocida` y origen `migracion`.
- **Estado:** Bloqueada. Motivo: no hay PostgreSQL ni Docker en la máquina de desarrollo y la instalación de `pgserver` fue rechazada por el control de permisos. Se desbloquea con PostgreSQL o Docker local, autorizando `pgserver` o con una URL de base de pruebas.
- **Referencia spec:** 0005.

## Fuera de este bloque

No se incluyen tareas de Pet, Pet-records, frontends, migración de datos ni integración con Datos Perú. Se abrirán en bloques propios.

---

# Bloque B — registro de usuarios de Paku con DNI (paku-backend)

Spec: `paku-backend/specs/features/0027-registro-con-dni/`. Plan: bloque B en `PAKU-HCVET-IMPLEMENTATION-PLAN.md`.

**Estado del bloque: completado en implementación** (aprobado por el usuario el 2026-11-28). No desplegado.

### Pendientes previos a producción del bloque B

| # | Pendiente | Responsable | Estado |
|---|---|---|---|
| B-P1 | Aprobación legal definitiva de la consulta de DNI en Datos Perú (su `docs/SPEC.md` 6.3, 11 y 12) | Usuario / legal | Pendiente |
| B-P2 | Correr `python -m scripts.diagnostico_dni` contra la base real, sanear a mano y aplicar `d2e7f1a9c4b8` y `e8f3a1c7d5b2` (Paku) y `0006` (Datos Perú) | El usuario lo ordena; se ejecuta en el servidor | Pendiente |
| B-P3 | Emitir la clave de Paku en Datos Perú solo con `dni_simple` y configurarla fuera del repositorio | Usuario | Pendiente |
| B-P4 | Probar registro, Google, regularización y «Mi perfil» en navegador y dispositivo contra un backend con Datos Perú | Usuario / QA | Pendiente |
| B-P5 | Activar `DNI_OBLIGATORIO` cuando paku-web y la app estén publicadas | Usuario | Pendiente |

| Orden | ID | Tarea | Repo | Depende de | Estado |
|---|---|---|---|---|---|
| 1 | PAKU-USERS-001 | Spec 0027 y dominio de usuarios | paku-backend | — | Completada |
| 2 | PAKU-USERS-002 | Formato y normalización del DNI | paku-backend | 001 | Completada |
| 3 | PAKU-USERS-003 | Unicidad del DNI entre cuentas | paku-backend | 002 | Completada |
| 4 | PAKU-USERS-004 | DNI obligatorio detrás de `DNI_OBLIGATORIO` | paku-backend | 003 | Completada |
| 5 | PAKU-USERS-005 | Regularización de usuarios sin DNI | paku-backend | 004 | Completada |
| 6 | PAKU-USERS-006 | Consulta de DNI protegida (puerto, límites, caché, errores) | paku-backend | 002 | Completada |
| 7 | PAKU-USERS-007 | Adaptador de Datos Perú | paku-backend, datosperu-backend | 006 y contrato de Datos Perú | Completada (sin desplegar; aprobación legal pendiente) |
| 8 | PAKU-USERS-008 | Frontends: DNI obligatorio, botón y autocompletado | paku-web, paku-vet-dev | 004, 006, 007 | Completada (sin verificar en navegador/dispositivo) |
| 9 | PAKU-USERS-009 | Índice único de `users.dni` tras sanear duplicados | paku-backend | bloque de migración | Completada (migración sin aplicar; diagnóstico pendiente en la base real) |

## PAKU-USERS-001 · Spec 0027 y dominio de usuarios
- **Objetivo:** spec, plan y tareas en `specs/features/0027-registro-con-dni/` y `specs/domain/usuarios.md` (AGENTS.md: dominio primero).
- **Criterios:** spec `approved` con escenarios Dado/cuando/entonces; fila en `specs/features/README.md`.
- **Estado:** Completada (2026-11-28). Spec 0027 (`in-progress`), plan, tareas y `specs/domain/usuarios.md`; fila en el índice; cambio C-66 para los fronts.

## PAKU-USERS-002 · Formato y normalización del DNI
- **Módulo:** `iam` (`domain/dni.py`, esquemas, casos de uso).
- **Criterios:** 8 dígitos; vacío o espacios = no enviado; 422 sin repetir el valor; aplica a registro, completar perfil, «Mi perfil» y alta por admin.
- **Pruebas:** unitarias de normalización y de cada flujo.
- **Estado:** Completada (2026-11-28). `domain/dni.py` (`normalizar_dni`) y tipo `Dni` en los cuatro esquemas de entrada. `tests/unit` de paku-backend: 545 en verde (37 nuevas en `tests/unit/test_registro_con_dni.py`).

## PAKU-USERS-003 · Unicidad del DNI entre cuentas
- **Criterios:** DNI de otra cuenta → 409 `DNI_ALREADY_REGISTERED` sin revelar la cuenta; el mismo DNI de la propia cuenta no choca; sin fusión automática.
- **Riesgo:** sin índice único en la base, dos registros simultáneos podrían colarse (PAKU-USERS-009).
- **Estado:** Completada (2026-11-28). `verificar_dni_disponible` en registro, completar perfil y «Mi perfil»; `get_by_dni` en el repositorio. Sin índice en la base (PAKU-USERS-009). `tests/unit` de paku-backend: 545 en verde (37 nuevas en `tests/unit/test_registro_con_dni.py`).

## PAKU-USERS-004 · DNI obligatorio detrás de `DNI_OBLIGATORIO`
- **Criterios:** con la opción activa, clientes sin DNI → 422 `DNI_REQUIRED` en registro y completado social; el guard de reservas exige DNI; groomers y admins no. Apagada: comportamiento actual.
- **Estado:** Completada (2026-11-28). `DNI_OBLIGATORIO` (apagada por defecto) en registro, completado social y guard de reservas; groomers y admins exentos. `tests/unit` de paku-backend: 545 en verde (37 nuevas en `tests/unit/test_registro_con_dni.py`).

## PAKU-USERS-005 · Regularización de usuarios sin DNI
- **Criterios:** el login no cambia; `GET /users/me` incluye `missing_profile_fields`; guardar el DNI en «Mi perfil» destraba la reserva sin volver a iniciar sesión.
- **Estado:** Completada (2026-11-28). `UserOut.missing_profile_fields`; el guard confirma el DNI en la base, así que guardar el DNI destraba la reserva sin nuevo login. `tests/unit` de paku-backend: 545 en verde (37 nuevas en `tests/unit/test_registro_con_dni.py`).

## PAKU-USERS-006 · Consulta de DNI protegida
- **Criterios:** `POST /users/me/dni/consulta` solo con sesión de cliente; devuelve nombres y apellidos; 5 por hora y 3 DNI distintos por día (429 con `Retry-After`); caché de 24 h; 404 `DNI_NOT_FOUND`, 503 `DNI_LOOKUP_UNAVAILABLE`; sin proveedor configurado → 503.
- **Estado:** Completada (2026-11-28). `POST /users/me/dni/consulta`, puerto `ConsultorDni`, límites por usuario (5/h, 3 DNI distintos/día) y caché de 24 h en memoria, errores 404/429/503; solo clientes. Responde 503 hasta PAKU-USERS-007. `tests/unit` de paku-backend: 545 en verde (37 nuevas en `tests/unit/test_registro_con_dni.py`).

## PAKU-USERS-007 · Adaptador de Datos Perú
- **Estado:** Completada (2026-11-28) en código y pruebas; **no desplegada**. Datos Perú: `POST /v1/dni/consulta` (spec 0008) con clave de cliente y `dni_simple`, proveedor activo por configuración, solo DNI/nombres/apellidos, límites por cliente (429 + `Retry-After`), auditoría técnica sin documento (migración `0006`, sin aplicar); `go test ./...` en verde. Paku: `ConsultorDniDatosPeru` con `DATOSPERU_URL`, `DATOSPERU_API_KEY` y `DATOSPERU_TIMEOUT_SEGUNDOS`; nombres legales separados del visible (migración `d2e7f1a9c4b8`, sin aplicar); cambio C-67. `tests/unit` de paku-backend: 576 en verde (31 nuevas en `tests/unit/test_consulta_dni_datosperu.py`, con Datos Perú simulado por `httpx.MockTransport`; ninguna consulta real).
- **Pendiente antes de producción:** aprobación legal definitiva en Datos Perú (su `docs/SPEC.md` 6.3, 11 y 12); aplicar `0006` y `d2e7f1a9c4b8`; emitir la clave de Paku con solo `dni_simple` y configurarla fuera del repositorio.

## PAKU-USERS-008 · Frontends
- **Alcance:** `paku-web` (registro, «Mi perfil») y `paku-vet-dev` (registro, completar perfil): DNI obligatorio, botón «Consultar DNI» y autocompletado, respetando el diseño actual.
- **Estado:** Completada en código (2026-11-28); **sin verificar en navegador ni dispositivo**. paku-web: DNI obligatorio en el registro, paso de DNI con sesión tras registro/Google/login sin DNI, «Consultar DNI» con espera de `Retry-After`, nombres legales aparte del visible y aviso de regularización en «Mi perfil». paku-vet-dev: lo mismo en registro y «Completa tu perfil» (registro con correo, social y regularización) con enrutamiento en `app/_layout.tsx`. Cambio C-68. paku-backend `tests/unit`: 597 en verde; paku-web `pnpm test:dni` 6/6 y ESLint limpio en los archivos tocados; paku-vet-dev sin errores de tipos nuevos (32 previos, los mismos antes y después).
- **Pendiente:** probar en navegador y en dispositivo contra un backend con Datos Perú configurado; activar `DNI_OBLIGATORIO` cuando ambos frontends estén publicados. En paku-vet-dev los cambios quedaron sobre una copia de trabajo con muchos cambios previos sin commit.

## PAKU-USERS-009 · Índice único de `users.dni`
- **Estado:** Completada en código (2026-11-28); **migración sin aplicar**. Migración `e8f3a1c7d5b2` (`uq_users_dni` parcial y `ck_users_dni_formato`) que se niega si hay datos inválidos o repetidos; diagnóstico de solo lectura `scripts/diagnostico_dni.py` (DNI enmascarados, sugerencias, sin cambios); el choque en la base responde 409. paku-backend `tests/unit`: 597 en verde; paku-web `pnpm test:dni` 6/6 y ESLint limpio en los archivos tocados; paku-vet-dev sin errores de tipos nuevos (32 previos, los mismos antes y después).
- **Pendiente antes de producción (obligatorio):** correr el diagnóstico contra la base real, sanear a mano y aplicar la migración cuando el usuario lo ordene.

---

# Bloque C — integración y vinculación de propietarios entre Paku y HCVet

Spec: `paku-backend/specs/features/0028-integracion-propietarios-hcvet/`. Plan: bloque C en
`PAKU-HCVET-IMPLEMENTATION-PLAN.md`. Requerimientos: §5, §6, §7 y §11. Contratos de HCVet (feature 0005) sin cambios.

| Orden | ID | Tarea | Repo | Depende de | Estado |
|---|---|---|---|---|---|
| 1 | PAKU-OWNERS-001 | Spec 0028, plan y tareas | paku-backend | Bloque B | Completada |
| 2 | PAKU-OWNERS-002 | Cliente de HCVet con API Key | paku-backend | 001, HCV-008 | Completada |
| 3 | PAKU-OWNERS-003 | Consentimientos con evidencia | paku-backend | 001 | Completada (textos provisionales) |
| 4 | PAKU-OWNERS-004 | Titularidad del DNI | paku-backend, hcvet-backend | Rectificación del usuario | Completada (requerimiento rectificado: sin verificación, D-105) |
| 5 | PAKU-OWNERS-005 | Vínculo, identificador HCVet y cola de operaciones | paku-backend | 002, 003 | Completada (migración sin aplicar) |
| 6 | PAKU-OWNERS-006 | Alta automática y vinculación sin duplicar ni contraseñas | paku-backend | 004, 005, 011 | Completada |
| 7 | PAKU-OWNERS-007 | Actualización controlada de datos básicos | paku-backend | 005 | Completada |
| 8 | PAKU-OWNERS-008 | Estados, idempotencia y reintentos | paku-backend | 005 | Completada |
| 9 | PAKU-OWNERS-009 | Frontends: consentimientos y estado | paku-web, paku-vet-dev | 003, 005 | Completada (sin verificar en navegador/dispositivo) |
| 10 | PAKU-OWNERS-010 | API de administración de la cola | paku-backend | 008 | Completada (sin UI en paku-admin) |
| 11 | PAKU-OWNERS-011 | HCVet: alta sin evidencia, vinculación de acceso básico y ampliación delegada | hcvet-backend | Rectificación | Completada (migración `e5a9c3f7d2b4` sin aplicar) |

Verificación (2026-11-28, tras la rectificación D-105): paku-backend `tests/unit` **653 en verde** (56 en
`tests/unit/test_integracion_hcvet.py`, HCVet simulado con `httpx.MockTransport`, ninguna llamada ni credencial real);
hcvet-backend `uv run pytest` **458 en verde**. `alembic heads`: `f4b2c8e1a7d3` (Paku) y `e5a9c3f7d2b4` (HCVet), ambas con
SQL de subida y bajada generado sin conectarse a ninguna base. paku-web `pnpm test:hcvet` 6/6 y ESLint limpio en los
archivos tocados. paku-vet-dev sin errores de tipos nuevos (los mismos 32 previos) y lógica idéntica a la web.

## PAKU-OWNERS-001 · Spec 0028
- **Estado:** Completada (2026-11-28). Spec con 23 escenarios, plan, tareas, fila en `specs/features/README.md` y cambio C-69.

## PAKU-OWNERS-002 · Cliente de HCVet
- **Criterios:** solo el backend usa la API Key (`HCVET_URL`, `HCVET_API_KEY`, fuera del repo); `Idempotency-Key` en el alta; fallas clasificadas en temporal (timeout, red, 5xx, 429 con `Retry-After`), conflicto (409), no encontrado (404) y permanente (401, 403, 422); errores sin DNI, teléfonos, correos ni la clave.
- **Estado:** Completada (2026-11-28). `app/modules/hcvet/infra/cliente.py`.

## PAKU-OWNERS-003 · Consentimientos con evidencia
- **Criterios:** cinco decisiones distintas sin valor por defecto; evidencia de solo inserción (versión, finalidad, canal, IP, agente, fecha); 409 si el texto cambió; rechazar no limita Paku.
- **Estado:** Completada (2026-11-28). `hcvet_consentimientos`, `GET /users/me/hcvet` y `PUT /users/me/hcvet/consentimientos`.
- **Pendiente antes de producción:** aprobar los textos legales (hoy `borrador-2026-11-28`, `TEXTOS_APROBADOS = False`).

## PAKU-OWNERS-004 · Titularidad del DNI
- **Estado:** Completada por **rectificación del requerimiento** (usuario, 2026-11-28; HCVet D-105). Paku no certifica que el DNI pertenece físicamente al cliente y no se implementa ninguna verificación presencial, biométrica ni fotográfica. La consulta a Datos Perú solo identifica el documento y autocompleta nombres. Se eliminó el puerto de titularidad y el estado `TITULARIDAD_NO_VERIFICADA`. Lo que protege la información ajena es el acceso básico de HCVet (PAKU-OWNERS-011).
- **Riesgo aceptado:** quien registre primero un DNI ajeno que no existía en HCVet crea ese propietario; se resuelve por soporte (spec 0028 §Titularidad).

## PAKU-OWNERS-005 · Vínculo, identificador HCVet y cola
- **Estado:** Completada (2026-11-28). `hcvet_vinculos` (`hcvet_propietario_id`, `hcvet_autorizacion_id`, DNI vinculado, estado) y `hcvet_operaciones` (entidad, tipo, id interno, id externo, clave de idempotencia, intentos, último error, creación y última sincronización). Migración `f4b2c8e1a7d3` **sin aplicar**.

## PAKU-OWNERS-006 · Alta automática y vinculación
- **Criterios:** alta sin evidencia con la integración concedida y datos completos; 409 → vinculación sin duplicar; recuperación de una autorización creada en un intento sin respuesta; sin contraseñas; acceso guardado (`completo`/`basico`); con acceso básico no se envían datos ni consentimientos y una revisión cada 6 h detecta si el dueño lo amplió.
- **Estado:** Completada (2026-11-28). Operativa al activar `HCVET_INTEGRACION_ACTIVA` (C-P4).

## PAKU-OWNERS-007 · Actualización controlada
- **Estado:** Completada (2026-11-28). Teléfono y nombres legales con `datos_al` y verificación por campo; el nombre visible no viaja; 409 → `conflicto`; con el vínculo vigente el DNI queda bloqueado en «Mi perfil» (409 `DNI_LOCKED_BY_HCVET`).

## PAKU-OWNERS-008 · Estados, idempotencia y reintentos
- **Estado:** Completada (2026-11-28). Estados `pendiente`, `bloqueado`, `sincronizando`, `sincronizado`, `fallido`, `conflicto` y `cancelado`; espera de 1 a 240 min, hasta 8 intentos; las colgadas más de 10 min se retoman con la misma clave; las dependientes esperan el vínculo sin gastar intentos; job cada minuto con `FOR UPDATE SKIP LOCKED`; `HCVET_INTEGRACION_ACTIVA=false` por defecto.

## PAKU-OWNERS-009 · Frontends
- **Estado:** Completada en código (2026-11-28); **sin verificar en navegador ni dispositivo**. paku-web: sección «Historial clínico (HCVet)» en «Mi perfil». paku-vet-dev: pantalla «Historial clínico» desde el menú del perfil. Opciones «Acepto / No acepto» sin preselección; el estado nunca muestra lo pendiente como conectado.

## PAKU-OWNERS-011 · HCVet: alta sin evidencia y vinculación de acceso básico (D-105)
- **Criterios:** `POST /v1/propietarios` acepta el alta sin `verificacion` (si viene, completa); la vinculación de una plataforma a un propietario existente es `basico` y no abre datos, mascotas, historiales ni consentimientos previos (404) ni permite actualizarlo; el dueño la amplía a `completo` con su sesión (auditado); `propietario_id` y `acceso` en las respuestas (compatibles).
- **Ampliación delegada (D-106, 2026-11-28):** el acceso completo también lo comunica otra plataforma con acceso completo y `autorizacion.otorgar`, solo con alcances que ella tiene y nunca para sí misma (origen `delegada`, `otorgada_por`, auditado); el dueño no necesita cuenta. Paku no pide ese alcance.
- **Estado:** Completada (2026-11-28). hcvet-backend `uv run pytest` **469 en verde** (D-105: 7 reescritas y 7 nuevas; D-106: 1 ajustada y 9 nuevas). Migración `e5a9c3f7d2b4` **sin aplicar**. D-105 en `DECISIONS.md`; D-086 reemplazada; DOMAIN, README, INTEGRACION, STATUS y spec 0005 rectificados.

## PAKU-OWNERS-010 · API de administración de la cola
- **Estado:** Completada (2026-11-28). `GET /admin/hcvet/operaciones` y `POST /admin/hcvet/operaciones/{id}/reintentar`, sin datos personales. No se hizo la pantalla en paku-admin.

### Pendientes previos a producción del bloque C

| # | Pendiente |
|---|---|
| C-P2 | Aprobar los textos legales de los cinco consentimientos y publicar su versión definitiva |
| C-P3 | Aplicar `f4b2c8e1a7d3` en Paku (después de B-P2) y `e5a9c3f7d2b4` en HCVet cuando el usuario lo ordene |
| C-P4 | Dar de alta a Paku como plataforma en HCVet, emitir su API Key, configurarla fuera del repositorio y activar `HCVET_INTEGRACION_ACTIVA` |
| C-P5 | HCV-014 (validar las migraciones del bloque A de HCVet en PostgreSQL) y desplegar HCVet con la feature 0005 |
| C-P6 | Probar las pantallas en navegador y en dispositivo |

### Decisiones registradas para el bloque Pet (no iniciado)

Aprobadas por el usuario el 2026-11-28 (HCVet D-107). Se implementan en el bloque Pet, con su spec:

1. Con acceso básico, Paku puede registrar mascotas nuevas para el propietario y consultar y actualizar solo las que él
   registró.
2. Puede registrar y consultar solo sus propios eventos sobre esas mascotas.
3. El acceso básico no permite consultar mascotas, datos personales ni eventos preexistentes ni de otras plataformas.
4. Se conserva la procedencia (plataforma que registró) de cada mascota y evento.
5. La asociación de una mascota nueva a un propietario preexistente bajo acceso básico es **provisional** y no altera
   sus relaciones de propiedad confirmadas.
6. Con acceso completo rigen los alcances y consentimientos correspondientes.
7. Sin verificaciones presenciales, biométricas ni contraseñas adicionales (D-105, D-106).
