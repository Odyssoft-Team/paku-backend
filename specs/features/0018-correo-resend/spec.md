---
feature: 0018-correo-resend
estado: in-progress
repos: [paku-backend, paku-admin]
creado: 2026-11-02
---

# Correo saliente con Resend

## Problema

Recordatorios y campañas necesitan enviar correos. El proveedor (Resend) y su API key deben configurarse desde el
admin, no en el servidor, y la key no puede quedar legible en la base de datos ni en el panel.

## Objetivo

El admin guarda y prueba la configuración del correo en Configuración → Integraciones; el backend envía por una
interfaz que no depende del proveedor.

## Fases

1. **Configuración y credenciales** (esta entrega): tabla `channel_providers`, cifrado Fernet, endpoints de
   configuración y prueba, `BaseEmailProvider` + `ResendEmailProvider` + factory. Admin: tarjeta «Correo».
2. Envío y registro: `notification_logs` (idempotency_key, PENDING/SENT/FAILED), `send_email(...)`, reintentos con
   APScheduler, historial «Envíos» en el admin.
3. Plantillas Jinja2 en el backend (layout base + una por tipo, HTML y texto) y primeros correos.
4. Webhook de Resend (entregado, rebote, queja), lista de bajas y enlace de baja en campañas.
5. Constructor visual de plantillas (bloques JSON armados con el mismo layout).

Remitente acordado: `Paku <hola@paku.com.pe>`, respuestas a `soporte@paku.com.pe`. El equipo verifica paku.com.pe
en Resend (SPF y DKIM en el DNS).

## Fuera de alcance (fase 1)

Enviar correos de negocio, registro de envíos, plantillas, webhooks, WhatsApp.

## Comportamiento esperado

1. **Dado** que no hay configuración, **cuando** el admin abre la tarjeta, **entonces** ve «Sin configurar» y Resend.
2. **Dado** una API key `re_…`, **cuando** se guarda, **entonces** queda cifrada y el panel solo ve `re_12…9aXz`.
3. **Dado** una key guardada, **cuando** se guarda sin escribir otra, **entonces** se conserva.
4. **Dado** que falta la key o el remitente, **cuando** se intenta activar, **entonces** 422 y no se guarda nada.
5. **Dado** una configuración guardada (activa o no), **cuando** se envía la prueba, **entonces** llega un correo al
   admin (u otro destinatario) y queda registrada la última prueba; si Resend la rechaza, se muestra el motivo.
6. **Dado** que el servidor no tiene `CREDENTIALS_ENCRYPTION_KEY`, **cuando** se guarda una key, **entonces** 503
   `ENCRYPTION_UNAVAILABLE` y el panel lo avisa.

## Criterios de aceptación

- [x] La key nunca se devuelve completa ni se guarda en claro.
- [x] Validación todo o nada con `field`.
- [x] Prueba de envío con resultado y última prueba.
- [ ] Probado en el servidor con el dominio paku.com.pe verificado en Resend.

## Impacto en el dominio

Estados del canal: `not_configured` (sin key o remitente), `disabled`, `active`, `error` (activo y falló la última
prueba). Cambiar key, proveedor o remitente borra la última prueba.
