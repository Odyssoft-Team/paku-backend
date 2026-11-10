---
feature: 0022-libro-de-reclamaciones
estado: in-progress
repos: [paku-backend, paku-web, paku-admin]
creado: 2026-11-09
---

# Libro de Reclamaciones virtual

## Problema

La web solo «preparaba» el reclamo en el navegador y mandaba al consumidor a una plataforma externa: no guardaba
nada. Culqi exige un Libro de Reclamaciones integrado en la web, sin formularios ni enlaces externos, para activar
el comercio. También es una obligación del proveedor ante INDECOPI.

## Objetivo

El consumidor registra su reclamo o queja en paku.com.pe, recibe una constancia con número y una copia por correo;
la empresa recibe un aviso y responde desde el admin dentro del plazo.

## Fuera de alcance

Libro físico de respaldo, reportes a INDECOPI (SIREC), adjuntos, feriados en el cálculo del plazo, prórrogas.

## Comportamiento esperado

1. **Dado** un consumidor sin sesión, **cuando** envía la hoja con sus datos, el bien contratado, el tipo (reclamo o
   queja), el detalle y su pedido, **entonces** se guarda con el siguiente correlativo del año (`LR-2026-000001`),
   la fecha, los datos del proveedor vigentes (razón social, RUC, domicilio) y el plazo de respuesta (15 días hábiles).
2. **Entonces** el consumidor ve la constancia y recibe la copia de su hoja por correo; la empresa recibe un aviso
   en el correo de reclamos (Configuración → Empresa; por defecto admin@paku.com.pe).
3. **Dado** un dato inválido, **entonces** 422 con el campo observado y no se consume número.
4. **Dado** un admin, **cuando** responde la hoja, **entonces** queda «Respondido» con fecha y autor, y la
   respuesta llega al correo del consumidor. Una hoja se responde una sola vez.
5. Si el correo falla, la hoja igual queda registrada (el envío queda en el registro de correos para reintentar).

## Criterios de aceptación

- [x] Correlativo único por año, sin huecos por envíos inválidos.
- [x] Los datos del proveedor se copian en la hoja.
- [x] Copia al consumidor, aviso a la empresa y respuesta por correo (vía feature 0018).
- [x] Admin: listar, ver la hoja completa, saber cuáles están vencidas y responder.
- [ ] Web: formulario integrado y constancia imprimible.
- [ ] Admin: pantalla de Libro de Reclamaciones.

## Impacto en el dominio

Entidad nueva `complaints` (hoja) con estados `received` → `answered`. Parámetros generales nuevos:
`company_legal_name`, `company_address`, `complaints_email`; `company_ruc` pasa a tener valor por defecto.

## Preguntas abiertas

- [ ] Validar con un abogado el texto final y si se requiere el libro físico de respaldo.
- [ ] Confirmar el domicilio que debe figurar (fiscal en SUNAT o de atención).
