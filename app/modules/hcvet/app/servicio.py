"""Casos de uso de la integración de propietarios con HCVet (feature 0028, bloque C).

- ``ServicioIntegracionHcvet``: lo que hace el cliente desde Paku (decidir consentimientos, ver el estado) y los
  avisos de cambios del perfil. Escribe en la base de Paku y encola operaciones; **nunca llama a HCVet**, así que
  responde igual con HCVet caído.
- ``ProcesadorHcvet``: el job del scheduler que envía las operaciones pendientes con reintentos.

Paku conserva el control de sus usuarios: los datos viven en Paku y HCVet recibe solo lo que el cliente autorizó.
Ninguna operación comercial (reservas, órdenes, tienda) depende de esta integración.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from app.modules.hcvet.domain import consentimientos as c
from app.modules.hcvet.domain import sincronizacion as s
from app.modules.hcvet.infra.cliente import CONFLICTO, NO_ENCONTRADO, TEMPORAL, ErrorHcvet, HcvetNoConfigurado
from app.modules.hcvet.infra.models import HcvetConsentimientoModel, HcvetOperacionModel, HcvetVinculoModel
from app.modules.hcvet.infra.repositorio import RepositorioHcvet

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UsuarioNoEncontrado(Exception):
    pass


def ultimos(filas: list[HcvetConsentimientoModel]) -> dict[str, HcvetConsentimientoModel]:
    """Estado vigente: la última decisión de cada tipo (las filas llegan en orden de registro)."""
    estado: dict[str, HcvetConsentimientoModel] = {}
    for fila in filas:
        estado[fila.tipo] = fila
    return estado


def campos_cambiados_para_hcvet(antes: Any, despues: Any) -> set[str]:
    """Campos notificables a HCVet que cambiaron en «Mi perfil» (usuarios de dominio de iam). El nombre visible no."""
    cambios: set[str] = set()
    if s.normalizar_telefono(antes.phone) != s.normalizar_telefono(despues.phone):
        cambios.add("telefono")
    previos, nuevos = antes.datos_legales, despues.datos_legales
    if (previos.nombres if previos else None) != (nuevos.nombres if nuevos else None):
        cambios.add("nombres")
    if (previos.apellidos if previos else None) != (nuevos.apellidos if nuevos else None):
        cambios.add("apellidos")
    return cambios


def _nueva_operacion(user_id: UUID, tipo: str, ahora: datetime, payload: Optional[dict] = None) -> HcvetOperacionModel:
    op_id = uuid4()
    return HcvetOperacionModel(
        id=op_id, user_id=user_id, entidad="propietario", tipo=tipo, estado=s.PENDIENTE,
        # Estable entre reintentos: HCVet devuelve la respuesta original con la misma clave (alta).
        clave_idempotencia=f"paku-{tipo}-{op_id}", payload=payload or {}, intentos=0, reintentable=False,
        creado_en=ahora, actualizado_en=ahora,
    )


class ServicioIntegracionHcvet:
    def __init__(self, repo: RepositorioHcvet, *, activa: bool, ahora: Callable[[], datetime] = _utcnow):
        self.repo = repo
        self.activa = activa
        self.ahora = ahora

    async def estado(self, user_id: UUID) -> dict[str, Any]:
        filas = await self.repo.consentimientos(user_id)
        vigentes = ultimos(filas)
        vinculo = await self.repo.vinculo(user_id)
        abiertas = [op for op in await self.repo.operaciones(user_id)
                    if op.estado in s.ABIERTOS and op.tipo not in s.TIPOS_DE_MANTENIMIENTO]
        if vinculo is None:
            integracion = {"estado": "sin_autorizar", "motivo": None, "faltan": [], "vinculado_en": None,
                           "acceso": None}
        else:
            motivo = vinculo.motivo
            if vinculo.estado == s.VINCULO_PENDIENTE and not self.activa:
                motivo = s.INTEGRACION_INACTIVA
            integracion = {
                "estado": vinculo.estado,
                "motivo": motivo,
                "faltan": (vinculo.detalle or "").split(",") if vinculo.motivo == s.DATOS_INCOMPLETOS else [],
                "vinculado_en": vinculo.vinculado_en,
                "acceso": vinculo.acceso if vinculo.estado == s.VINCULADO else None,
            }
        return {
            "integracion": integracion,
            "operaciones_pendientes": len(abiertas),
            "textos_aprobados": c.TEXTOS_APROBADOS,
            "consentimientos": [
                {
                    "tipo": tipo,
                    "titulo": c.TEXTOS[tipo].titulo,
                    "texto": c.TEXTOS[tipo].texto,
                    "version_texto": c.VERSION_TEXTOS,
                    "decision": (
                        {
                            "concedido": vigentes[tipo].concedido,
                            "version_texto": vigentes[tipo].version_texto,
                            "registrado_en": vigentes[tipo].registrado_en,
                        }
                        if tipo in vigentes
                        else None
                    ),
                }
                for tipo in c.TIPOS
            ],
        }

    async def decidir(self, user_id: UUID, decisiones: list[c.Decision], *, canal: str, ip: Optional[str],
                      user_agent: Optional[str]) -> dict[str, Any]:
        """Registra las decisiones (evidencia de solo inserción) y encola lo que haya que avisar a HCVet."""
        c.validar_decisiones(decisiones)
        if canal not in c.CANALES:
            raise c.DecisionInvalida("Canal desconocido.")
        if await self.repo.usuario(user_id) is None:
            raise UsuarioNoEncontrado()
        ahora = self.ahora()
        vigentes = ultimos(await self.repo.consentimientos(user_id))
        cambios: list[HcvetConsentimientoModel] = []
        for d in decisiones:
            anterior = vigentes.get(d.tipo)
            if anterior is not None and anterior.concedido == d.concedido and anterior.version_texto == d.version_texto:
                continue  # misma decisión sobre el mismo texto: no se duplica la evidencia
            fila = HcvetConsentimientoModel(
                id=uuid4(), user_id=user_id, tipo=d.tipo, concedido=d.concedido, version_texto=d.version_texto,
                finalidad=c.TEXTOS[d.tipo].finalidad, canal=canal, ip=(ip or None) and ip[:64],
                user_agent=(user_agent or None) and user_agent[:300], registrado_en=ahora,
            )
            await self.repo.agregar_consentimiento(fila)
            cambios.append(fila)

        if cambios:
            await self._efectos(user_id, cambios, ahora)
            await self.repo.confirmar()
        return await self.estado(user_id)

    async def _efectos(self, user_id: UUID, cambios: list[HcvetConsentimientoModel], ahora: datetime) -> None:
        vinculo = await self.repo.vinculo(user_id, bloquear=True)
        operaciones = await self.repo.operaciones(user_id)
        orden = iter(range(1_000))

        def momento() -> datetime:  # conserva el orden de envío dentro de una misma decisión
            return ahora + timedelta(microseconds=next(orden))

        integracion = next((f for f in cambios if f.tipo == c.INTEGRACION), None)
        vinculado = vinculo is not None and vinculo.estado == s.VINCULADO

        # 1) Consentimientos de HCVet de un propietario ya vinculado (antes de una posible revocación: después Paku
        #    ya no puede registrarlos). Si el alta está pendiente, el alta lleva las decisiones vigentes al enviarse.
        #    Con acceso básico no: Paku no cambia los consentimientos de un propietario que ya existía (D-105).
        if vinculado and vinculo.acceso != s.ACCESO_BASICO:
            for fila in cambios:
                if fila.tipo in c.TIPOS_HCVET:
                    await self.repo.agregar_operacion(
                        _nueva_operacion(user_id, s.CONSENTIMIENTO, momento(), {"consentimiento_id": str(fila.id),
                                                                                 "tipo": fila.tipo}))

        if integracion is None:
            return
        if integracion.concedido:
            if vinculado:
                return
            if vinculo is None:
                vinculo = HcvetVinculoModel(user_id=user_id, creado_en=ahora)
            vinculo.estado, vinculo.motivo, vinculo.detalle, vinculo.actualizado_en = s.VINCULO_PENDIENTE, None, None, ahora
            await self.repo.guardar_vinculo(vinculo)
            if not any(op.tipo == s.ALTA and op.estado in s.ABIERTOS for op in operaciones):
                await self.repo.agregar_operacion(_nueva_operacion(user_id, s.ALTA, momento()))
            return

        # Revocación de la integración: no se envía nada nuevo en nombre del cliente; lo ya registrado en HCVet se
        # conserva (REQUIREMENTS §6). Si hay vínculo, se revoca la autorización de Paku en HCVet.
        for op in operaciones:
            if op.tipo in (s.ALTA, s.ACTUALIZACION, s.REVISION_ACCESO) and op.estado in (
                s.PENDIENTE, s.BLOQUEADO, s.FALLIDO):
                op.estado, op.motivo, op.reintentable, op.actualizado_en = s.CANCELADO, s.INTEGRACION_REVOCADA, False, ahora
                await self.repo.guardar_operacion(op)
        if vinculo is None:
            return
        if vinculado and vinculo.hcvet_autorizacion_id:
            await self.repo.agregar_operacion(_nueva_operacion(
                user_id, s.REVOCACION, momento(), {"autorizacion_id": vinculo.hcvet_autorizacion_id}))
        vinculo.estado, vinculo.motivo, vinculo.actualizado_en = s.VINCULO_REVOCADO, s.INTEGRACION_REVOCADA, ahora
        await self.repo.guardar_vinculo(vinculo)

    async def notificar_cambio_perfil(self, user_id: UUID, campos: set[str]) -> None:
        """Encola la actualización de datos básicos en HCVet (solo los notificables y si ya está vinculado)."""
        campos = {campo for campo in campos if campo in s.CAMPOS_NOTIFICABLES}
        if not campos:
            return
        vinculo = await self.repo.vinculo(user_id)
        if vinculo is None or vinculo.estado != s.VINCULADO:
            return  # el alta, cuando ocurra, lleva los datos vigentes
        if vinculo.acceso == s.ACCESO_BASICO:
            return  # sin acceso a los datos del propietario que ya existía (D-105): no se sobrescriben
        ahora = self.ahora()
        pendiente = next((op for op in await self.repo.operaciones(user_id)
                          if op.tipo == s.ACTUALIZACION and op.estado in (s.PENDIENTE, s.BLOQUEADO)), None)
        if pendiente is not None:  # se agrupa: se envían los valores vigentes al procesarla
            pendiente.payload = {"campos": sorted(set(pendiente.payload.get("campos", [])) | campos)}
            pendiente.actualizado_en = ahora
            await self.repo.guardar_operacion(pendiente)
        else:
            await self.repo.agregar_operacion(_nueva_operacion(user_id, s.ACTUALIZACION, ahora,
                                                               {"campos": sorted(campos)}))
        await self.repo.confirmar()

    async def dni_bloqueado(self, user_id: UUID) -> bool:
        """Con el propietario vinculado (o enviándose) el DNI no se cambia en Paku: identifica al propietario en HCVet."""
        vinculo = await self.repo.vinculo(user_id)
        return vinculo is not None and vinculo.estado in (s.VINCULADO, s.VINCULO_SINCRONIZANDO)


class ProcesadorHcvet:
    """Envía las operaciones vencidas. Un intento por operación y corrida; los reintentos siguen ``proximo_intento``."""

    def __init__(self, repo: RepositorioHcvet, cliente: Any, *, activa: bool, ahora: Callable[[], datetime] = _utcnow):
        self.repo = repo
        self.cliente = cliente
        self.activa = activa
        self.ahora = ahora

    async def procesar(self, limite: int = 50) -> dict[str, int]:
        if not self.activa or not self.cliente.configurado:
            return {"tomadas": 0}
        ahora = self.ahora()
        tomadas = await self.repo.tomar_vencidas(ahora, limite)
        # Se marcan todas como "sincronizando" y se confirma: libera los bloqueos sin que otra instancia las tome.
        anteriores = {op.id: op.estado for op in tomadas}
        for op in tomadas:
            op.estado, op.actualizado_en = s.SINCRONIZANDO, ahora
            await self.repo.guardar_operacion(op)
        await self.repo.confirmar()
        resultado: dict[str, int] = {"tomadas": len(tomadas)}
        for op in tomadas:
            try:
                await self._procesar(op, anteriores[op.id])
            except HcvetNoConfigurado:
                self._volver(op, anteriores[op.id], None)
            except Exception:  # no se sabe si llegó: se reintenta con la misma clave
                logger.exception("Operación HCVet %s falló de forma inesperada", op.id)
                await self._fallo(op, await self.repo.vinculo(op.user_id),
                                  ErrorHcvet(TEMPORAL, "Error inesperado al enviar a HCVet."))
            await self.repo.guardar_operacion(op)
            await self.repo.confirmar()
            resultado[op.estado] = resultado.get(op.estado, 0) + 1
        return resultado

    async def reintentar(self, op_id: UUID) -> Optional[HcvetOperacionModel]:
        """Reintento manual (admin) de una operación fallida o en conflicto: vuelve a la cola sin perder su clave."""
        op = await self.repo.operacion(op_id)
        if op is None or op.estado not in (s.FALLIDO, s.CONFLICTO, s.BLOQUEADO):
            return op
        op.estado, op.reintentable, op.proximo_intento_en, op.actualizado_en = s.PENDIENTE, False, None, self.ahora()
        op.intentos = 0
        await self.repo.guardar_operacion(op)
        await self.repo.confirmar()
        return op

    # --- por tipo ---

    async def _procesar(self, op: HcvetOperacionModel, anterior: str) -> None:
        usuario = await self.repo.usuario(op.user_id)
        if usuario is None:
            self._cerrar(op, s.CANCELADO, "USUARIO_ELIMINADO")
            return
        vinculo = await self.repo.vinculo(op.user_id)
        filas = await self.repo.consentimientos(op.user_id)
        if op.tipo == s.ALTA:
            await self._alta(op, usuario, filas, vinculo)
        elif op.tipo == s.REVOCACION:
            await self._revocacion(op, vinculo)
        elif op.tipo == s.REVISION_ACCESO:
            await self._revision_acceso(op, vinculo, filas)
        elif vinculo is None or vinculo.estado in (s.VINCULO_FALLIDO, s.VINCULO_CONFLICTO) or (
            vinculo.estado == s.VINCULO_REVOCADO and not await self._revocacion_pendiente(op)
        ):
            self._cerrar(op, s.CANCELADO, s.AUTORIZACION_NO_VIGENTE)
        elif vinculo.estado not in (s.VINCULADO, s.VINCULO_REVOCADO):
            # Depende del alta: espera sin gastar intentos (REQUIREMENTS §11, operaciones dependientes).
            self._volver(op, s.PENDIENTE, s.ESPERA_VINCULO, en=timedelta(minutes=5))
        elif vinculo.estado == s.VINCULADO and vinculo.acceso == s.ACCESO_BASICO:
            self._cerrar(op, s.CANCELADO, s.ACCESO_BASICO_MOTIVO)
        elif op.tipo == s.CONSENTIMIENTO:
            await self._consentimiento(op, filas, vinculo)
        elif op.tipo == s.ACTUALIZACION:
            await self._actualizacion(op, usuario, vinculo)
        else:
            self._cerrar(op, s.FALLIDO, s.RECHAZADO, "Tipo de operación desconocido.")

    async def _revocacion_pendiente(self, op) -> bool:
        """Lo encolado antes de revocar todavía se envía: la autorización sigue vigente hasta que se revoque en HCVet."""
        return any(o.tipo == s.REVOCACION and o.estado in s.ABIERTOS and o.creado_en > op.creado_en
                   for o in await self.repo.operaciones(op.user_id))

    async def _alta(self, op, usuario, filas, vinculo) -> None:
        vigentes = ultimos(filas)
        integracion = vigentes.get(c.INTEGRACION)
        if integracion is None or not integracion.concedido:
            self._cerrar(op, s.CANCELADO, s.INTEGRACION_REVOCADA)
            return
        if vinculo is None:
            vinculo = HcvetVinculoModel(user_id=op.user_id, estado=s.VINCULO_PENDIENTE, creado_en=self.ahora())
        if vinculo.estado == s.VINCULADO:
            self._cerrar(op, s.SINCRONIZADO, None)
            return

        datos, faltan = s.datos_para_hcvet(usuario, await self.repo.distrito(op.user_id))
        faltan += [f"decision_{t}" for t in c.REQUERIDOS_PARA_ALTA if t not in vigentes]
        if faltan:
            await self._bloquear(op, vinculo, s.DATOS_INCOMPLETOS, ",".join(faltan))
            return
        # Sin evidencia de titularidad (HCVet D-105): DNI, datos básicos, consentimientos y la API Key bastan.

        ahora = self.ahora()
        op.intentos += 1
        vinculo.estado, vinculo.motivo, vinculo.detalle, vinculo.actualizado_en = s.VINCULO_SINCRONIZANDO, None, None, ahora
        await self.repo.guardar_vinculo(vinculo)
        await self.repo.guardar_operacion(op)
        await self.repo.confirmar()

        cuerpo = {
            "propietario": {
                "dni": datos.dni, "nombres": datos.nombres, "apellidos": datos.apellidos, "distrito": datos.distrito,
                "telefono": datos.telefono, "email": datos.email,
                "permite_indexacion_veterinaria": vigentes[c.INDEXACION].concedido,
                "permite_uso_comercial": vigentes[c.USO_COMERCIAL].concedido,
            },
            "alcances": list(c.ALCANCES_PAKU),
            "version_terminos": integracion.version_texto,
            "consentimientos": [
                {"tipo": t, "concedido": vigentes[t].concedido, "finalidad": vigentes[t].finalidad}
                for t in c.TIPOS_INICIALES_HCVET if t in vigentes
            ],
        }
        try:
            registrado = await self.cliente.registrar_propietario(cuerpo, clave_idempotencia=op.clave_idempotencia)
        except ErrorHcvet as error:
            if error.tipo != CONFLICTO:
                await self._fallo(op, vinculo, error)
                return
            # El DNI ya existe en HCVet (otra plataforma, el dueño o un vínculo anterior revocado): vinculación sin
            # crear otro propietario ni contraseñas. HCVet la da con acceso básico (D-105).
            await self._vincular_existente(op, vinculo, datos.dni, cuerpo, vigentes)
            return
        await self._vinculado(op, vinculo, datos.dni, propietario_id=registrado["propietario_id"],
                              autorizacion_id=registrado["autorizacion_id"], nuevo=bool(registrado.get("nuevo")),
                              acceso=registrado.get("acceso") or s.ACCESO_COMPLETO)

    async def _vincular_existente(self, op, vinculo, dni: str, cuerpo_alta: dict, vigentes) -> None:
        cuerpo = {k: cuerpo_alta[k] for k in ("alcances", "version_terminos")}
        try:
            autorizacion = await self.cliente.otorgar_autorizacion(dni, cuerpo)
        except ErrorHcvet as error:
            if error.tipo != CONFLICTO:
                await self._fallo(op, vinculo, error)
                return
            # Puede que la autorización se haya creado en un intento anterior sin respuesta: se recupera.
            try:
                propias = await self.cliente.listar_autorizaciones(dni)
            except ErrorHcvet as error_lista:
                await self._fallo(op, vinculo, error_lista)
                return
            autorizacion = next((a for a in propias if a.get("vigente")), None)
            if autorizacion is None:
                await self._fallo(op, vinculo, error)
                return
        acceso = autorizacion.get("acceso") or s.ACCESO_BASICO
        await self._vinculado(op, vinculo, dni, propietario_id=autorizacion.get("propietario_id"),
                              autorizacion_id=autorizacion["id"], nuevo=False, acceso=acceso)
        await self._tras_vinculo(op.user_id, vigentes, acceso)

    async def _tras_vinculo(self, user_id, vigentes, acceso: str) -> None:
        """Con acceso completo, se registran en HCVet las decisiones que el cliente tomó en Paku. Con acceso básico no
        se tocan los consentimientos del propietario existente: se revisa cada tanto si el dueño amplió el acceso."""
        ahora = self.ahora()
        if acceso == s.ACCESO_BASICO:
            revision = _nueva_operacion(user_id, s.REVISION_ACCESO, ahora)
            revision.proximo_intento_en = ahora + timedelta(hours=s.REVISION_ACCESO_HORAS)
            await self.repo.agregar_operacion(revision)
            return
        for i, tipo in enumerate(c.TIPOS_HCVET):
            if tipo in vigentes:
                await self.repo.agregar_operacion(_nueva_operacion(
                    user_id, s.CONSENTIMIENTO, ahora + timedelta(microseconds=i),
                    {"consentimiento_id": str(vigentes[tipo].id), "tipo": tipo}))

    async def _revision_acceso(self, op, vinculo, filas) -> None:
        """Vínculo básico: ¿el dueño amplió el acceso de Paku? Lo hace con su sesión en HCVet o por medio de otra
        plataforma con acceso completo y ``autorizacion.otorgar`` (HCVet D-106); Paku nunca se lo da a sí mismo."""
        if vinculo is None or vinculo.estado != s.VINCULADO or vinculo.acceso != s.ACCESO_BASICO:
            self._cerrar(op, s.CANCELADO, None)
            return
        try:
            propias = await self.cliente.listar_autorizaciones(vinculo.dni_vinculado)
        except ErrorHcvet as error:
            if error.tipo == TEMPORAL:
                self._volver(op, s.PENDIENTE, s.HCVET_NO_DISPONIBLE, en=timedelta(hours=1))
                return
            await self._fallo(op, vinculo, error, afecta_vinculo=error.tipo == NO_ENCONTRADO)
            return
        vigente = next((a for a in propias if a.get("vigente")), None)
        if vigente is None:
            await self._fallo(op, vinculo, ErrorHcvet(NO_ENCONTRADO, "Paku ya no tiene autorización vigente en HCVet."),
                              afecta_vinculo=True)
            return
        if (vigente.get("acceso") or s.ACCESO_BASICO) == s.ACCESO_BASICO:
            self._volver(op, s.PENDIENTE, s.ACCESO_BASICO_MOTIVO, en=timedelta(hours=s.REVISION_ACCESO_HORAS))
            return
        vinculo.acceso, vinculo.hcvet_autorizacion_id = s.ACCESO_COMPLETO, vigente["id"]
        vinculo.motivo, vinculo.actualizado_en = None, self.ahora()
        await self.repo.guardar_vinculo(vinculo)
        self._cerrar(op, s.SINCRONIZADO, None, id_externo=str(vigente["id"]))
        await self._tras_vinculo(op.user_id, ultimos(filas), s.ACCESO_COMPLETO)

    async def _vinculado(self, op, vinculo, dni: str, *, propietario_id: Optional[int], autorizacion_id: int,
                         nuevo: bool, acceso: str) -> None:
        ahora = self.ahora()
        vinculo.estado, vinculo.detalle, vinculo.acceso = s.VINCULADO, None, acceso
        vinculo.motivo = s.ACCESO_BASICO_MOTIVO if acceso == s.ACCESO_BASICO else None
        vinculo.hcvet_propietario_id, vinculo.hcvet_autorizacion_id = propietario_id, autorizacion_id
        vinculo.dni_vinculado, vinculo.nuevo_en_hcvet = dni, nuevo
        vinculo.vinculado_en = vinculo.actualizado_en = ahora
        await self.repo.guardar_vinculo(vinculo)
        self._cerrar(op, s.SINCRONIZADO, None, id_externo=str(propietario_id or autorizacion_id))
        # Si el cliente revocó mientras el alta estaba en curso, se revoca enseguida.
        integracion = ultimos(await self.repo.consentimientos(op.user_id)).get(c.INTEGRACION)
        if integracion is not None and not integracion.concedido:
            await self.repo.agregar_operacion(_nueva_operacion(op.user_id, s.REVOCACION, ahora,
                                                               {"autorizacion_id": autorizacion_id}))
            vinculo.estado, vinculo.motivo = s.VINCULO_REVOCADO, s.INTEGRACION_REVOCADA

    async def _consentimiento(self, op, filas, vinculo) -> None:
        fila = next((f for f in filas if str(f.id) == op.payload.get("consentimiento_id")), None)
        if fila is None:
            self._cerrar(op, s.CANCELADO, s.RECHAZADO, "Consentimiento no encontrado.")
            return
        op.intentos += 1
        try:
            await self.cliente.registrar_consentimiento(
                vinculo.dni_vinculado, fila.tipo,
                {"concedido": fila.concedido, "finalidad": fila.finalidad, "version_texto": fila.version_texto})
        except ErrorHcvet as error:
            await self._fallo(op, vinculo, error, afecta_vinculo=error.tipo == NO_ENCONTRADO)
            return
        self._cerrar(op, s.SINCRONIZADO, None)

    async def _actualizacion(self, op, usuario, vinculo) -> None:
        cuerpo: dict[str, Any] = {}
        campos = set(op.payload.get("campos", []))
        if "telefono" in campos and (telefono := s.normalizar_telefono(usuario.phone)):
            cuerpo["telefono"] = telefono
        verificaciones: dict[str, dict] = {}
        for campo, valor in (("nombres", usuario.legal_first_name), ("apellidos", usuario.legal_last_name)):
            if campo in campos and valor:
                cuerpo[campo] = valor.strip()[:100]
                if usuario.legal_data_source == "datosperu" and usuario.legal_data_checked_at:
                    verificaciones[campo] = {"metodo": s.METODO_VERIFICACION_NOMBRES,
                                             "fecha": usuario.legal_data_checked_at.date().isoformat(),
                                             "referencia": "paku:consulta-dni"}
        if not cuerpo:
            self._cerrar(op, s.CANCELADO, s.DATOS_INCOMPLETOS, "No hay datos válidos que enviar.")
            return
        datos_al = usuario.updated_at or self.ahora()
        if datos_al.tzinfo is None:
            datos_al = datos_al.replace(tzinfo=timezone.utc)
        cuerpo["datos_al"] = datos_al.isoformat()
        if verificaciones:
            cuerpo["verificaciones"] = verificaciones
        op.intentos += 1
        try:
            await self.cliente.actualizar_propietario(vinculo.dni_vinculado, cuerpo)
        except ErrorHcvet as error:
            # 409: HCVet tiene un dato más reciente o verificado. No se sobrescribe ni se reintenta.
            await self._fallo(op, vinculo, error, afecta_vinculo=error.tipo == NO_ENCONTRADO)
            return
        self._cerrar(op, s.SINCRONIZADO, None)

    async def _revocacion(self, op, vinculo) -> None:
        autorizacion_id = op.payload.get("autorizacion_id")
        if vinculo is None or not vinculo.dni_vinculado or not autorizacion_id:
            self._cerrar(op, s.CANCELADO, s.AUTORIZACION_NO_VIGENTE)
            return
        op.intentos += 1
        try:
            await self.cliente.revocar_autorizacion(vinculo.dni_vinculado, int(autorizacion_id))
        except ErrorHcvet as error:
            if error.tipo != NO_ENCONTRADO:  # 404: ya no estaba vigente, que es lo que se quería
                await self._fallo(op, None, error)
                return
        self._cerrar(op, s.SINCRONIZADO, None)

    # --- estados ---

    def _cerrar(self, op, estado: str, motivo: Optional[str], error: Optional[str] = None, *,
                id_externo: Optional[str] = None) -> None:
        ahora = self.ahora()
        op.estado, op.motivo, op.ultimo_error = estado, motivo, error
        op.reintentable, op.proximo_intento_en, op.actualizado_en = False, None, ahora
        if estado == s.SINCRONIZADO:
            op.sincronizado_en = ahora
            op.id_externo = id_externo or op.id_externo

    def _volver(self, op, estado: str, motivo: Optional[str], *, en: Optional[timedelta] = None) -> None:
        ahora = self.ahora()
        op.estado, op.motivo, op.actualizado_en = estado, motivo, ahora
        op.proximo_intento_en = ahora + en if en else None

    async def _bloquear(self, op, vinculo, motivo: str, detalle: Optional[str]) -> None:
        self._volver(op, s.BLOQUEADO, motivo, en=timedelta(minutes=s.REVISION_BLOQUEADAS_MINUTOS))
        op.ultimo_error = detalle
        vinculo.estado, vinculo.motivo, vinculo.detalle, vinculo.actualizado_en = (
            s.VINCULO_BLOQUEADO, motivo, detalle, self.ahora())
        await self.repo.guardar_vinculo(vinculo)

    async def _fallo(self, op, vinculo, error: ErrorHcvet, *, afecta_vinculo: Optional[bool] = None) -> None:
        """Temporal → reintento con espera (hasta MAX_INTENTOS). 409 → conflicto. Lo demás → fallido sin reintento."""
        ahora = self.ahora()
        op.ultimo_error, op.actualizado_en = error.mensaje, ahora
        afecta = op.tipo == s.ALTA if afecta_vinculo is None else afecta_vinculo
        if error.tipo == TEMPORAL:
            proximo = s.proximo_intento(op.intentos, ahora=ahora, retry_after=error.retry_after)
            op.estado, op.reintentable, op.proximo_intento_en = s.FALLIDO, proximo is not None, proximo
            op.motivo = s.HCVET_NO_DISPONIBLE if proximo else s.REINTENTOS_AGOTADOS
            estado_vinculo = s.VINCULO_PENDIENTE if proximo else s.VINCULO_FALLIDO
        elif error.tipo == CONFLICTO:
            op.estado, op.motivo, op.reintentable, op.proximo_intento_en = s.CONFLICTO, s.CONFLICTO_HCVET, False, None
            estado_vinculo = s.VINCULO_CONFLICTO
        else:
            motivo = s.AUTORIZACION_NO_VIGENTE if error.tipo == NO_ENCONTRADO else s.RECHAZADO
            op.estado, op.motivo, op.reintentable, op.proximo_intento_en = s.FALLIDO, motivo, False, None
            estado_vinculo = s.VINCULO_FALLIDO
        if afecta and vinculo is not None:
            vinculo.estado, vinculo.motivo, vinculo.detalle, vinculo.actualizado_en = (
                estado_vinculo, op.motivo, None, ahora)
            await self.repo.guardar_vinculo(vinculo)


async def procesar_operaciones_hcvet_job() -> None:
    """Scheduler: envía a HCVet las operaciones pendientes y los reintentos vencidos."""
    from app.core.db import AsyncSessionLocal
    from app.core.settings import settings
    from app.modules.hcvet.infra.cliente import cliente_desde_settings
    from app.modules.hcvet.infra.repositorio import PostgresRepositorioHcvet

    if not settings.HCVET_INTEGRACION_ACTIVA:
        return
    try:
        async with AsyncSessionLocal() as session:
            resultado = await ProcesadorHcvet(
                PostgresRepositorioHcvet(session), cliente_desde_settings(), activa=True
            ).procesar()
            if resultado.get("tomadas"):
                logger.info("procesar_operaciones_hcvet_job %s", resultado)
    except Exception:
        logger.exception("procesar_operaciones_hcvet_job failed")
