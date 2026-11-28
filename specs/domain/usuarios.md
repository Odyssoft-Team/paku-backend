# Dominio — Usuarios (identidad y DNI)

> Módulo backend: `app/modules/iam/`
> Estado del doc: 🟡 parcial (solo identidad y DNI; feature 0027)
> Última verificación contra código: 2026-11-28

## Qué es

La cuenta de una persona en Paku (cliente, groomer o administrador) y sus datos de identidad.

## Reglas de negocio (DNI)

- El DNI tiene **8 dígitos**. Un valor vacío o con espacios cuenta como no enviado.
- Es **único entre cuentas**: un DNI usado por otra cuenta responde 409 `DNI_ALREADY_REGISTERED`, sin decir cuál. No se
  crean cuentas duplicadas ni se fusionan.
- Con `DNI_OBLIGATORIO=true`, un **cliente** (rol `user`) necesita DNI para completar su perfil: registro con correo,
  completado de perfil social (Google, Facebook, Apple u otros) y para reservar u ordenar. Groomers y administradores no.
- El inicio de sesión **no** exige DNI: un cliente existente sin DNI entra y ve `missing_profile_fields: ["dni"]`.
- El DNI es editable desde «Mi perfil» mientras no exista verificación de titularidad ni vínculo con HCVet, si no lo
  tiene otra cuenta.
- La unicidad se valida en la aplicación y en la base (`uq_users_dni`, migración `e8f3a1c7d5b2`, obligatoria antes de
  producción). Un choque en la base también responde 409. Los datos inválidos o repetidos se revisan con
  `scripts/diagnostico_dni.py` y se corrigen a mano: nunca se eliminan ni fusionan usuarios automáticamente.

## Consulta de DNI

- `POST /users/me/dni/consulta` con sesión de cliente. Devuelve solo nombres y apellidos para autocompletar.
- Límites por usuario: 5 consultas por hora y 3 DNI distintos por día (429 con `Retry-After`). Caché de 24 horas.
- Si Datos Perú responde 429 (su límite), Paku responde 429 con el mismo `Retry-After`.
- Errores: 422 formato, 404 `DNI_NOT_FOUND`, 503 `DNI_LOOKUP_UNAVAILABLE`.
- No es un buscador: solo sirve para identificar al propio usuario. Consultar un DNI no prueba titularidad.
- Proveedor: Datos Perú (`POST /v1/dni/consulta` con la clave de cliente de Paku). Sin `DATOSPERU_URL` o
  `DATOSPERU_API_KEY`, responde 503. Paku no elige el proveedor de Datos Perú.

## Nombre legal y nombre visible

- `first_name` y `last_name` son el nombre visible: lo escribe el usuario.
- `legal_first_name`, `legal_last_name`, `legal_data_source` y `legal_data_checked_at` son los nombres oficiales
  del DNI. Solo los llena el servidor, cuando el usuario guarda un DNI que consultó; el cliente no puede enviarlos.
- Si el DNI cambia sin consultarlo, los nombres legales se borran.
- **Consulta de datos oficiales ≠ verificación de titularidad:** los nombres legales no prueban que el usuario sea
  el titular del DNI. La verificación de titularidad no existe todavía.

## Vínculo con HCVet (feature 0028)

- El cliente decide cinco consentimientos (ninguno por defecto); su evidencia se guarda en `hcvet_consentimientos`.
- Con `integracion_hcvet` concedido, Paku lo registra o lo vincula en HCVet como propietario, sin contraseña, y guarda
  la referencia en `hcvet_vinculos`, sin verificación de titularidad (HCVet D-105). Si ya existía en HCVet, el
  vínculo es de acceso básico: no comparte lo registrado antes hasta que el dueño lo autorice en HCVet.
- Los nombres legales son los que viajan a HCVet; el nombre visible nunca.
- Con el vínculo vigente el DNI no se cambia desde «Mi perfil».
- Rechazar o revocar no limita los servicios de Paku.
