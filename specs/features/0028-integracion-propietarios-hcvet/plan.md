# Plan — 0028 integración de propietarios con HCVet

## paku-backend

Módulo nuevo `app/modules/hcvet/`:

| Archivo | Qué |
|---|---|
| `domain/consentimientos.py` | Tipos, textos provisionales versionados, `ALCANCES_PAKU`, validación de decisiones |
| `domain/sincronizacion.py` | Estados, motivos, espera entre reintentos, saneamiento de errores, datos del propietario, política de actualización |
| `infra/cliente.py` | `ClienteHcvet` (httpx): alta con `Idempotency-Key`, autorizaciones, consentimientos, PATCH; clasificación de fallas |
| `infra/models.py` | `hcvet_consentimientos` (solo inserción), `hcvet_vinculos`, `hcvet_operaciones` (outbox) |
| `infra/repositorio.py` | Postgres; `tomar_vencidas` con `FOR UPDATE SKIP LOCKED` |
| `app/servicio.py` | `ServicioIntegracionHcvet` (decidir, estado, avisos de perfil, bloqueo de DNI) y `ProcesadorHcvet` (job) |
| `api/router.py` | `GET /users/me/hcvet`, `PUT /users/me/hcvet/consentimientos`, `GET /admin/hcvet/operaciones`, `POST /admin/hcvet/operaciones/{id}/reintentar` |

Cambios en código existente: `PUT /users/me` (bloqueo de DNI vinculado y aviso de cambios), `main.py` (rutas),
`core/scheduler.py` (job cada minuto), `core/settings.py` y `.env.example` (`HCVET_*`), `alembic/env.py`.

Migración `f4b2c8e1a7d3` (revisa `e8f3a1c7d5b2`): solo tablas nuevas e índices, entre ellos una sola alta abierta por
cliente y un propietario de HCVet por cuenta. **No aplicada.**

Reutilización: patrón de reintentos de la feature 0018 (correos), scheduler APScheduler existente, contratos de la
feature 0005 de HCVet sin cambios.

## paku-web

`lib/hcvet.ts` (lógica pura), `lib/api/hcvet.ts`, `components/account/HcvetConsentSection.tsx` en «Mi perfil».
Prueba: `pnpm test:hcvet`.

## paku-vet-dev

`src/utils/hcvet.ts` (copia de la web), `src/api/services/hcvet.service.ts`, pantalla
`app/(tabs)/(user)/(menu)/historial-clinico.tsx` y entrada «Historial clínico (HCVet)» en el menú del perfil.

## Decisiones técnicas menores (tomadas)

- Nombres y apellidos enviados a HCVet = nombres legales (Datos Perú), no el nombre visible; sin ellos, `DATOS_INCOMPLETOS`.
- Distrito = el de la dirección principal (o la más reciente); en esta versión no se notifican cambios de dirección.
- Alcances pedidos: `propietario.*`, `mascota.consultar`, `mascota.registrar`, `historial.consultar`, `evento.registrar`
  (los de mascotas y eventos se piden ya para no volver a pedir autorización en Pet y Pet-records).
- Rectificación D-105 (HCVet): sin evidencia de titularidad. Se eliminó `domain/titularidad.py`. HCVet agrega
  `acceso` (`completo`/`basico`) a las autorizaciones y `propietario_id` a `AutorizacionLeida`; Paku guarda ambos.
- Vínculo básico: operación de mantenimiento `revisar_acceso` cada 6 h (`GET …/autorizaciones`); no cuenta como
  cambio pendiente del cliente. Al pasar a completo se registran en HCVet los consentimientos del cliente.
- Reintento manual del admin reinicia el contador de intentos y conserva la clave de idempotencia.
- IP y agente de usuario se guardan como evidencia del consentimiento.

## hcvet-backend (D-105)

`autorizaciones.acceso` (migración `e5a9c3f7d2b4`, sin ejecutar); `permisos.cargar` ignora las básicas (404 en datos,
mascotas, historiales y consentimientos); `PropietarioRegistrar.verificacion` opcional; la vinculación de una plataforma
es básica; el dueño la amplía con su sesión (revoca la básica y crea la completa, auditado).
