# Plan — registro con DNI

Spec: [spec.md](spec.md) (aprobado).

## Enfoque

1. **Dominio** (`app/modules/iam/domain/dni.py`): `normalizar_dni` (vacío → None; 8 dígitos o error) y
   `campos_faltantes(user, exigir_dni)` (teléfono, sexo, fecha de nacimiento y, si se exige, DNI).
2. **Configuración** (`app/core/settings.py`): `DNI_OBLIGATORIO` (apagada), límites y caché de la consulta.
3. **Casos de uso** (`profile.py`): `RegisterUser`, `CompleteProfile` y `UpdateProfile` validan formato y unicidad
   (`repo.get_by_dni`) y exigen DNI a clientes cuando la opción está activa. Errores con `code` estable.
4. **Guard de reservas** (`app/core/auth.py`): con la opción activa, consulta la base y exige DNI además de los tres
   datos actuales; `missing_fields` indica lo que falta.
5. **Regularización**: `UserOut.missing_profile_fields` (campo agregado, compatible).
6. **Consulta de DNI**: puerto `ConsultorDni` y caso de uso `ConsultarDni` con límites por usuario y caché en memoria;
   ruta `POST /users/me/dni/consulta`. Adaptador `ConsultorDniDatosPeru` (`httpx`, `POST /v1/dni/consulta`, clave
   de cliente, un intento, timeout) cuando hay `DATOSPERU_URL` y `DATOSPERU_API_KEY`; si no, `ConsultorDniNoDisponible`.
7. **Nombres legales**: `User.datos_legales` (columnas `legal_*`). `RegisterUser`, `UpdateProfile` y
   `CompleteProfile` reciben `buscar_datos_oficiales` (la caché de la consulta) y los llenan al guardar el DNI.

## Cambios por repo

| Repo | Cambio |
|---|---|
| paku-backend | Todo lo anterior y pruebas en `tests/unit/test_registro_con_dni.py` y `tests/unit/test_consulta_dni_datosperu.py`. |
| paku-web, paku-vet-dev | DNI obligatorio en registro, completar perfil y «Mi perfil»; botón «Consultar DNI» y autocompletado. Pendiente: fuera de los directorios de esta sesión y el botón depende de Datos Perú. |
| datosperu-backend | `POST /v1/dni/consulta` con clave de cliente (su spec 0008). Hecho; producción espera la aprobación legal. |

## Migraciones

`d2e7f1a9c4b8_users_legal_names.py`: columnas opcionales `legal_first_name`, `legal_last_name`, `legal_data_source`
y `legal_data_checked_at` en `users`. Creada, **no aplicada**.

`e8f3a1c7d5b2_users_dni_unique_index.py` (PAKU-USERS-009): `uq_users_dni` (único parcial, `dni IS NOT NULL`) y
`ck_users_dni_formato`. Antes de crearlos cuenta inválidos y repetidos y, si hay, se niega (no corrige datos).
Diagnóstico previo de solo lectura: `scripts/diagnostico_dni.py`. Creada, **no aplicada**.

## Frontends (PAKU-USERS-008)

- **paku-web:** `lib/dni.ts` (lógica pura, `pnpm test:dni`), `components/account/DniLookupField.tsx`,
  `components/common/DniOnboardingStep.tsx` (paso con sesión tras registro, Google o login sin DNI),
  `AuthDialog` (DNI obligatorio), «Mi perfil» (consulta, nombres legales y aviso de regularización).
- **paku-vet-dev:** `src/utils/dni.ts` (copia de la lógica + `debeCompletarPerfil`),
  `src/api/services/dni.service.ts`, `src/components/common/DniLookupField.tsx`, registro con DNI obligatorio,
  «Completa tu perfil» reutilizada para registro con correo, social y regularización, y enrutamiento en
  `app/_layout.tsx`.
