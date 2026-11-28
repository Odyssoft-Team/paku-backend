---
feature: 0027-registro-con-dni
estado: in-progress   # Bloque B completado en implementación (2026-11-28); sin desplegar. Pendientes previos a producción B-P1 a B-P5 en PAKU-HCVET-TASKS.md
repos: [paku-backend, paku-web, paku-vet-dev, datosperu-backend]
creado: 2026-11-28
---

# Registro de usuarios con DNI (bloque B de la integración Paku–HCVet)

Requerimientos: `specs/integracion-hcvet/PAKU-HCVET-REQUIREMENTS.md` §4 y §13. Tareas: `PAKU-USERS-001` a `PAKU-USERS-009`
en `specs/integracion-hcvet/PAKU-HCVET-TASKS.md`.

## Problema

- El DNI es opcional en el registro con correo, en el completado de perfil social y en «Mi perfil». No se valida su
  formato (`users.dni` es texto libre de 30) y dos cuentas pueden tener el mismo DNI.
- La integración con HCVet identifica al propietario por DNI: sin DNI obligatorio, único y válido no se puede vincular.
- No existe una consulta de DNI para autocompletar nombres y apellidos.

## Objetivo

Que todo cliente de Paku complete su perfil con un DNI válido y único, sin romper el inicio de sesión ni las apps
actuales, con un camino de regularización para los usuarios existentes, y con una consulta de DNI protegida contra el
abuso conectada a la consulta de DNI para clientes de Datos Perú (su spec 0008).

## Fuera de alcance

- Registrar o vincular propietarios en HCVet (bloque A ya listo del lado de HCVet; la integración es otro bloque).
- Pet, Pet-records y migración de datos.
- Sanear automáticamente DNI inválidos o repetidos: el diagnóstico solo informa; no se eliminan ni fusionan usuarios.
- Verificar titularidad del DNI (no se hace con una consulta de nombres).

## Comportamiento esperado

### Formato y unicidad

1. **Dado** un DNI enviado en registro, completado de perfil, «Mi perfil» o alta por el administrador, **cuando** no
   tiene 8 dígitos, **entonces** responde 422 sin repetir el valor. Un DNI vacío o con espacios cuenta como no enviado.
2. **Dado** un DNI que ya tiene otra cuenta, **cuando** se intenta usar, **entonces** responde 409 `DNI_ALREADY_REGISTERED`
   sin indicar qué cuenta lo tiene. No se crean cuentas duplicadas ni se fusionan.
3. **Dado** el mismo DNI que ya tiene la propia cuenta, **cuando** se vuelve a enviar, **entonces** no hay conflicto.

### DNI obligatorio (con `DNI_OBLIGATORIO=true`)

4. **Dado** el registro con correo de un cliente (rol `user`), **cuando** no envía DNI, **entonces** responde 422
   `DNI_REQUIRED`.
5. **Dado** un usuario de Google, Facebook, Apple u otro proveedor, **cuando** completa su perfil sin DNI, **entonces**
   responde 422 `DNI_REQUIRED`. El inicio de sesión social no cambia.
6. **Dado** un cliente existente sin DNI, **cuando** inicia sesión, **entonces** entra normalmente; `GET /users/me` indica
   `missing_profile_fields: ["dni"]` para mostrar la regularización.
7. **Dado** un cliente sin DNI, **cuando** intenta reservar u ordenar, **entonces** responde 403 `PROFILE_INCOMPLETE` con
   `missing_fields` que incluye `dni`. Al guardar su DNI en «Mi perfil», puede continuar sin volver a iniciar sesión.
8. **Dado** `DNI_OBLIGATORIO=false` (valor por defecto), **cuando** un cliente no envía DNI, **entonces** todo funciona
   como antes (compatibilidad con las apps actuales); el formato y la unicidad sí se validan si lo envía.
9. **Dado** el alta de un groomer o administrador por el administrador, **cuando** no envía DNI, **entonces** se permite.

### Consulta de DNI

10. **Dado** un cliente con sesión, **cuando** consulta un DNI válido, **entonces** recibe solo nombres y apellidos para
    autocompletar. Sin sesión: 401.
11. **Dado** un cliente que supera el límite de consultas (por hora o de DNI distintos por día), **cuando** consulta otra
    vez, **entonces** responde 429 con `Retry-After`.
12. **Dado** un DNI inexistente, el servicio no disponible, un timeout o un error del proveedor, **cuando** se consulta,
    **entonces** responde 404 `DNI_NOT_FOUND` o 503 `DNI_LOOKUP_UNAVAILABLE`; el cliente puede escribir sus datos a mano.
13. **Dado** el mismo DNI consultado otra vez dentro de la ventana de caché, **cuando** se consulta, **entonces** no se
    vuelve a llamar al proveedor.
14. **Dado** que faltan `DATOSPERU_URL` o `DATOSPERU_API_KEY`, **cuando** se consulta, **entonces** responde 503
    `DNI_LOOKUP_UNAVAILABLE`. Con ambas, se consulta `POST {DATOSPERU_URL}/v1/dni/consulta` con la clave de cliente de
    Paku (solo `dni_simple`); nunca el token de administrador. Paku no elige el proveedor. Un solo intento: 404 de Datos
    Perú → 404; 429 de Datos Perú → 429 `DNI_LOOKUP_RATE_LIMITED` con su `Retry-After` (60 s si falta, entre 1 s y
    un día); 401, 403, 422, 5xx, timeout, error de red o respuesta inesperada → 503. La clave y el DNI no van a los
    logs.

### Nombres legales (separados del nombre visible)

15. **Dado** un cliente de cualquier método de registro (correo y contraseña, Google, Facebook, Apple u otro) que ya
    tiene sesión, **cuando** consulta su DNI y luego lo guarda (`PUT /users/me` o `PUT /users/me/complete`),
    **entonces** la cuenta guarda los nombres oficiales en `legal_first_name`, `legal_last_name`, con
    `legal_data_source` (`datosperu`) y `legal_data_checked_at`. `first_name` y `last_name` (nombre visible) no cambian.
16. **Dado** un DNI guardado sin consulta previa del servidor, **cuando** se guarda, **entonces** no hay nombres
    legales. Si el DNI cambia sin consultarlo, los nombres legales anteriores se borran (eran de otro DNI); si no
    cambia, se conservan.
17. **Dado** un cliente, **cuando** envía nombres legales en su perfil, **entonces** se ignoran: solo los llena el
    servidor a partir de su consulta. Los nombres legales son datos oficiales del DNI, **no** una verificación de
    titularidad (no prueban que el usuario sea el titular).

### Índice único (PAKU-USERS-009)

18. **Dado** que existen DNI inválidos o repetidos en `users`, **cuando** se aplica la migración `e8f3a1c7d5b2`,
    **entonces** se niega con el conteo y pide correr `python -m scripts.diagnostico_dni` (solo lectura, DNI
    enmascarados). No modifica, elimina ni fusiona usuarios.
19. **Dado** dos cuentas que guardan el mismo DNI a la vez, **cuando** la base rechaza la segunda por `uq_users_dni`,
    **entonces** responde 409 `DNI_ALREADY_REGISTERED` (no 500).

### Frontends (PAKU-USERS-008)

20. **Dado** el registro con correo en la web o la app, **cuando** el cliente se registra, **entonces** el DNI es
    obligatorio (8 dígitos) y, ya con la sesión creada, se le ofrece «Consultar DNI» para guardar sus nombres legales.
21. **Dado** un inicio de sesión social nuevo, **cuando** completa su perfil, **entonces** pide teléfono, sexo, fecha de
    nacimiento y DNI con «Consultar DNI».
22. **Dado** un cliente existente sin DNI, **cuando** entra, **entonces** se le pide regularizarlo (web: paso tras el
    login y aviso en «Mi perfil»; app: «Completa tu perfil»). Puede dejarlo para después mientras el backend no lo
    exija (`missing_profile_fields` sin `dni`).
23. **Dado** un 429 de la consulta, **cuando** se muestra, **entonces** el botón espera los segundos de `Retry-After`.
    El nombre visible nunca se reemplaza con el nombre legal.

## Criterios de aceptación

- [x] Escenarios 1 a 19 con pruebas unitarias (`test_registro_con_dni.py`, `test_consulta_dni_datosperu.py`,
      `test_indice_unico_dni.py`).
- [x] Suite de `tests/unit` en verde (597).
- [x] Escenarios 20 a 23 en paku-web y paku-vet-dev (lógica probada con `node --test`; pantallas sin prueba en
      navegador ni dispositivo).
- [x] `DNI_OBLIGATORIO` documentado; apagado por defecto.
- [ ] Migración `d2e7f1a9c4b8` (nombres legales) aplicada: solo cuando el usuario lo ordene.
- [ ] Índice único: correr el diagnóstico contra la base real, sanear a mano y aplicar `e8f3a1c7d5b2` (antes de
      producción).

## Impacto en el dominio

`specs/domain/usuarios.md` (nuevo): DNI de 8 dígitos, único entre cuentas, obligatorio para completar el perfil de un
cliente cuando la opción está activa; consulta de DNI protegida; nombres legales separados del nombre visible.

## Decisiones (aprobadas por el usuario el 2026-11-28)

- `DNI_OBLIGATORIO` apagado hasta actualizar los frontends: las apps actuales envían el DNI como opcional y
  exigirlo de golpe rompería su registro.
- Unicidad en la aplicación (409). El índice único en la base es obligatorio antes de producción (PAKU-USERS-009).
- El DNI es editable mientras no exista verificación de titularidad ni vínculo con HCVet (siempre que no lo tenga
  otra cuenta).
- Límites de la consulta: 5 por hora por usuario y 3 DNI distintos por día; caché de 24 horas.
- Nombre legal separado del nombre visible: columnas `legal_*` llenadas por el servidor desde la consulta.
- Detalles técnicos (aprobados el 2026-11-28): timeout de 5 s (`DATOSPERU_TIMEOUT_SEGUNDOS`), un solo intento, los
  nombres legales salen de la caché de la consulta (24 h) al guardar el DNI.
- Detalles técnicos (Claude, PAKU-USERS-008/009): 429 de Datos Perú → 429 con su `Retry-After`; índice único
  parcial `uq_users_dni` más `ck_users_dni_formato`; la migración se niega con datos sucios; en los frontends el DNI
  es obligatorio y «Hacerlo después» solo existe mientras el backend no exija el DNI.

## Preguntas abiertas

- [x] Datos Perú: endpoint `POST /v1/dni/consulta` para clientes (su spec 0008, 2026-11-28).
- [x] Nombre legal frente a nombre de visualización: separados (2026-11-28).
- [ ] **Antes de producción:** aprobación legal definitiva de la consulta en Datos Perú; emitir la clave de Paku con
      solo `dni_simple` y configurarla fuera del repositorio.
