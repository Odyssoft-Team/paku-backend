"""Feature 0028 (bloque C): integración de propietarios con HCVet.

HCVet se simula con ``httpx.MockTransport`` y la base con un repositorio en memoria: ninguna llamada real, ninguna
credencial real. Sin evidencia de titularidad (HCVet D-105): el alta usa DNI, datos básicos, consentimientos y la
API Key; la vinculación a un propietario que ya existía es de acceso básico.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest

from app.core.auth import CurrentUser
from app.modules.hcvet.app.servicio import (
    ProcesadorHcvet,
    ServicioIntegracionHcvet,
    campos_cambiados_para_hcvet,
)
from app.modules.hcvet.domain import consentimientos as c
from app.modules.hcvet.domain import sincronizacion as s
from app.modules.hcvet.infra.cliente import (
    CONFLICTO,
    NO_ENCONTRADO,
    PERMANENTE,
    TEMPORAL,
    ClienteHcvet,
    ConfiguracionHcvet,
    ErrorHcvet,
    HcvetNoConfigurado,
)
from app.modules.hcvet.infra.models import HcvetOperacionModel
from app.modules.iam.domain.user import DatosLegales

DNI = "45678912"
CLAVE_FALSA = "hcv_prueba_no_real"
AHORA = datetime(2026, 11, 28, 15, 0, tzinfo=timezone.utc)


def correr(coro):
    return asyncio.run(coro)


# --- Dobles ---


class Reloj:
    def __init__(self, inicio: datetime = AHORA):
        self.t = inicio

    def __call__(self) -> datetime:
        return self.t

    def avanzar(self, **kw) -> None:
        self.t += timedelta(**kw)


def usuario(**cambios) -> SimpleNamespace:
    base = dict(
        id=uuid4(), email="ana@example.com", phone="987 654 321", dni=DNI, first_name="Anita", last_name="P",
        legal_first_name="ANA MARIA", legal_last_name="PEREZ ROJAS", legal_data_source="datosperu",
        legal_data_checked_at=AHORA - timedelta(days=1), updated_at=AHORA - timedelta(hours=1),
    )
    base.update(cambios)
    return SimpleNamespace(**base)


class RepoFalso:
    def __init__(self):
        self.usuarios: dict[UUID, SimpleNamespace] = {}
        self.distritos: dict[UUID, str] = {}
        self.filas: list = []
        self.vinculos: dict = {}
        self.ops: list[HcvetOperacionModel] = []
        self.confirmaciones = 0

    def agregar_usuario(self, u, distrito: str | None = "Miraflores"):
        self.usuarios[u.id] = u
        if distrito:
            self.distritos[u.id] = distrito
        return u

    async def usuario(self, user_id):
        return self.usuarios.get(user_id)

    async def distrito(self, user_id):
        return self.distritos.get(user_id)

    async def consentimientos(self, user_id):
        return [f for f in self.filas if f.user_id == user_id]

    async def agregar_consentimiento(self, fila):
        self.filas.append(fila)

    async def vinculo(self, user_id, *, bloquear=False):
        return self.vinculos.get(user_id)

    async def guardar_vinculo(self, vinculo):
        self.vinculos[vinculo.user_id] = vinculo

    async def operaciones(self, user_id):
        return sorted((o for o in self.ops if o.user_id == user_id), key=lambda o: o.creado_en)

    async def agregar_operacion(self, op):
        self.ops.append(op)

    async def guardar_operacion(self, op):
        if op not in self.ops:
            self.ops.append(op)

    async def operacion(self, op_id):
        return next((o for o in self.ops if o.id == op_id), None)

    async def tomar_vencidas(self, ahora, limite):
        def vencida(o):
            a_tiempo = o.proximo_intento_en is None or o.proximo_intento_en <= ahora
            if o.estado in (s.PENDIENTE, s.BLOQUEADO):
                return a_tiempo
            if o.estado == s.FALLIDO:
                return o.reintentable and a_tiempo
            if o.estado == s.SINCRONIZANDO:
                return o.actualizado_en <= ahora - timedelta(minutes=s.COLGADA_MINUTOS)
            return False

        return sorted((o for o in self.ops if vencida(o)), key=lambda o: o.creado_en)[:limite]

    async def listar_operaciones(self, estado, limite):
        return [o for o in self.ops if estado is None or o.estado == estado][:limite]

    async def confirmar(self):
        self.confirmaciones += 1

    def de(self, user_id, tipo=None):
        return [o for o in self.ops if o.user_id == user_id and (tipo is None or o.tipo == tipo)]


class HcvetSimulado:
    """Respuestas programadas por (método, ruta). Cada valor: lista de respuestas o una sola que se repite."""

    def __init__(self, respuestas: dict | None = None):
        self.respuestas = respuestas or {}
        self.solicitudes: list[httpx.Request] = []

    def _manejar(self, request: httpx.Request) -> httpx.Response:
        self.solicitudes.append(request)
        clave = (request.method, request.url.path.removeprefix("/v1"))
        respuesta = self.respuestas.get(clave)
        if respuesta is None:
            return httpx.Response(500, json={"detail": "sin respuesta programada"})
        if isinstance(respuesta, list):
            respuesta = respuesta.pop(0) if len(respuesta) > 1 else respuesta[0]
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    def cliente(self, *, url="https://hcvet.test/v1", clave=CLAVE_FALSA) -> ClienteHcvet:
        return ClienteHcvet(ConfiguracionHcvet(url, clave, 5), transport=httpx.MockTransport(self._manejar))

    def cuerpos(self, metodo, ruta):
        return [json.loads(r.content) for r in self.solicitudes
                if r.method == metodo and r.url.path.removeprefix("/v1") == ruta]


ALTA_OK = httpx.Response(201, json={"propietario_id": 77, "dni": DNI, "nuevo": True, "autorizacion_id": 501,
                                   "acceso": "completo"})
VINCULO_BASICO = httpx.Response(201, json={"id": 900, "propietario_id": 55, "acceso": "basico", "vigente": True})
CONFLICTO_DNI = httpx.Response(409, json={"detail": f"El DNI {DNI} ya está registrado en HCVet."})
TODO_CONCEDIDO = [c.Decision(t, True, c.VERSION_TEXTOS) for t in c.TIPOS]


def servicio(repo, reloj=None, activa=True):
    return ServicioIntegracionHcvet(repo, activa=activa, ahora=reloj or Reloj())


def procesador(repo, hcvet: HcvetSimulado, reloj=None, activa=True):
    return ProcesadorHcvet(repo, hcvet.cliente(), activa=activa, ahora=reloj or Reloj())


def preparar(decisiones=None, **datos_usuario):
    repo = RepoFalso()
    u = repo.agregar_usuario(usuario(**datos_usuario))
    correr(servicio(repo).decidir(u.id, decisiones or TODO_CONCEDIDO, canal="web", ip="10.0.0.1",
                                  user_agent="pytest"))
    return repo, u


def vincular(repo, u, hcvet=None, reloj=None):
    hcvet = hcvet or HcvetSimulado({("POST", "/propietarios"): ALTA_OK})
    correr(procesador(repo, hcvet, reloj).procesar())
    assert repo.vinculos[u.id].estado == s.VINCULADO
    return hcvet


# --- Cliente de HCVet ---


def test_cliente_envia_la_api_key_y_la_clave_de_idempotencia():
    hcvet = HcvetSimulado({("POST", "/propietarios"): ALTA_OK})
    datos = correr(hcvet.cliente().registrar_propietario({"x": 1}, clave_idempotencia="paku-alta-1"))
    assert datos["propietario_id"] == 77
    solicitud = hcvet.solicitudes[0]
    assert solicitud.headers["Authorization"] == f"Bearer {CLAVE_FALSA}"
    assert solicitud.headers["Idempotency-Key"] == "paku-alta-1"
    assert str(solicitud.url) == "https://hcvet.test/v1/propietarios"


@pytest.mark.parametrize(
    "respuesta, tipo",
    [
        (httpx.Response(503), TEMPORAL),
        (httpx.Response(500, text="no json"), TEMPORAL),
        (httpx.Response(429, headers={"Retry-After": "30"}), TEMPORAL),
        (CONFLICTO_DNI, CONFLICTO),
        (httpx.Response(404, json={"detail": "No existe"}), NO_ENCONTRADO),
        (httpx.Response(401, json={"detail": "x"}), PERMANENTE),
        (httpx.Response(403, json={"detail": "Sin alcance"}), PERMANENTE),
        (httpx.Response(422, json={"detail": [{"loc": ["body", "telefono"], "msg": "inválido"}]}), PERMANENTE),
        (httpx.ConnectError("caído"), TEMPORAL),
        (httpx.ReadTimeout("lento"), TEMPORAL),
    ],
)
def test_cliente_clasifica_cada_falla(respuesta, tipo):
    hcvet = HcvetSimulado({("PATCH", f"/propietarios/{DNI}"): respuesta})
    with pytest.raises(ErrorHcvet) as error:
        correr(hcvet.cliente().actualizar_propietario(DNI, {}))
    assert error.value.tipo == tipo
    assert error.value.reintentable is (tipo == TEMPORAL)


def test_cliente_conserva_retry_after_y_no_guarda_datos_personales():
    hcvet = HcvetSimulado({("POST", "/propietarios"): httpx.Response(429, headers={"Retry-After": "120"})})
    with pytest.raises(ErrorHcvet) as limitado:
        correr(hcvet.cliente().registrar_propietario({}, clave_idempotencia="k"))
    assert limitado.value.retry_after == 120

    hcvet = HcvetSimulado({("POST", "/propietarios"): CONFLICTO_DNI})
    with pytest.raises(ErrorHcvet) as conflicto:
        correr(hcvet.cliente().registrar_propietario({}, clave_idempotencia="k"))
    assert DNI not in conflicto.value.mensaje and "[número]" in conflicto.value.mensaje
    assert CLAVE_FALSA not in str(conflicto.value)


def test_cliente_sin_configurar_no_llama():
    hcvet = HcvetSimulado()
    with pytest.raises(HcvetNoConfigurado):
        correr(hcvet.cliente(url="", clave="").registrar_propietario({}, clave_idempotencia="k"))
    assert hcvet.solicitudes == []


def test_sin_datos_personales_oculta_dni_telefono_y_correo():
    texto = s.sin_datos_personales("DNI 45678912, tel 987654321, correo ana@example.com")
    assert "45678912" not in texto and "987654321" not in texto and "ana@example.com" not in texto


# --- Consentimientos ---


def test_ningun_consentimiento_viene_marcado_y_el_estado_inicial_es_sin_autorizar():
    repo = RepoFalso()
    u = repo.agregar_usuario(usuario())
    estado = correr(servicio(repo).estado(u.id))
    assert estado["integracion"]["estado"] == "sin_autorizar"
    assert [x["tipo"] for x in estado["consentimientos"]] == list(c.TIPOS)
    assert all(x["decision"] is None for x in estado["consentimientos"])
    assert estado["textos_aprobados"] is False


@pytest.mark.parametrize(
    "decisiones, error",
    [
        ([c.Decision(c.INTEGRACION, True, "version-vieja")], c.VersionDeTextoDesactualizada),
        ([c.Decision("cualquiera", True, c.VERSION_TEXTOS)], c.DecisionInvalida),
        ([c.Decision(c.HISTORIAL, True, c.VERSION_TEXTOS)] * 2, c.DecisionInvalida),
        ([], c.DecisionInvalida),
    ],
)
def test_decisiones_invalidas_no_se_registran(decisiones, error):
    repo = RepoFalso()
    u = repo.agregar_usuario(usuario())
    with pytest.raises(error):
        correr(servicio(repo).decidir(u.id, decisiones, canal="app", ip=None, user_agent=None))
    assert repo.filas == [] and repo.ops == []


def test_la_evidencia_conserva_version_fecha_canal_y_origen():
    repo, u = preparar()
    fila = next(f for f in repo.filas if f.tipo == c.INTEGRACION)
    assert (fila.concedido, fila.version_texto, fila.canal, fila.ip, fila.user_agent) == (
        True, c.VERSION_TEXTOS, "web", "10.0.0.1", "pytest")
    assert fila.registrado_en == AHORA
    assert fila.finalidad == c.TEXTOS[c.INTEGRACION].finalidad


def test_autorizar_la_integracion_encola_una_sola_alta_y_repetir_no_duplica():
    repo, u = preparar()
    assert len(repo.de(u.id, s.ALTA)) == 1
    assert repo.vinculos[u.id].estado == s.VINCULO_PENDIENTE
    filas = len(repo.filas)
    correr(servicio(repo).decidir(u.id, TODO_CONCEDIDO, canal="app", ip=None, user_agent=None))
    assert len(repo.filas) == filas and len(repo.de(u.id, s.ALTA)) == 1


def test_rechazar_la_integracion_no_encola_nada():
    repo, u = preparar([c.Decision(t, False, c.VERSION_TEXTOS) for t in c.TIPOS])
    assert repo.ops == [] and u.id not in repo.vinculos
    assert correr(servicio(repo).estado(u.id))["integracion"]["estado"] == "sin_autorizar"


def test_solo_el_modulo_hcvet_y_mi_perfil_dependen_de_la_integracion():
    """Paku funciona comercialmente sin HCVet: reservas, órdenes y tienda no importan este módulo."""
    raiz = Path(__file__).resolve().parents[2] / "app"
    permitidos = {raiz / "main.py", raiz / "core" / "scheduler.py", raiz / "modules" / "iam" / "api" / "router.py"}
    usan = {p for p in raiz.rglob("*.py") if "modules.hcvet" in p.read_text(encoding="utf-8")
            and (raiz / "modules" / "hcvet") not in p.parents}
    assert usan <= permitidos


# --- Sin verificación de titularidad (HCVet D-105) ---


def test_el_alta_automatica_no_exige_ni_envia_evidencia_de_titularidad():
    repo, u = preparar()
    hcvet = vincular(repo, u)
    cuerpo = hcvet.cuerpos("POST", "/propietarios")[0]
    assert "verificacion" not in cuerpo
    assert repo.de(u.id, s.ALTA)[0].intentos == 1
    estado = correr(servicio(repo).estado(u.id))["integracion"]
    assert (estado["estado"], estado["acceso"]) == ("vinculado", "completo")


# --- Alta y vinculación ---


def test_datos_incompletos_bloquean_el_alta_con_la_lista_de_faltantes():
    repo = RepoFalso()
    u = repo.agregar_usuario(usuario(phone=None, legal_first_name=None), distrito=None)
    correr(servicio(repo).decidir(u.id, [c.Decision(c.INTEGRACION, True, c.VERSION_TEXTOS)], canal="web", ip=None,
                                  user_agent=None))
    hcvet = HcvetSimulado()
    correr(procesador(repo, hcvet).procesar())
    estado = correr(servicio(repo).estado(u.id))["integracion"]
    assert estado["motivo"] == s.DATOS_INCOMPLETOS
    assert set(estado["faltan"]) == {"nombres_legales", "telefono", "distrito", "decision_indexacion_veterinaria",
                                     "decision_uso_comercial"}
    assert hcvet.solicitudes == []


def test_integracion_apagada_no_envia_y_lo_informa():
    repo, u = preparar()
    hcvet = HcvetSimulado({("POST", "/propietarios"): ALTA_OK})
    assert correr(procesador(repo, hcvet, activa=False).procesar()) == {"tomadas": 0}
    assert hcvet.solicitudes == [] and repo.de(u.id, s.ALTA)[0].estado == s.PENDIENTE
    assert correr(servicio(repo, activa=False).estado(u.id))["integracion"]["motivo"] == s.INTEGRACION_INACTIVA


def test_alta_nueva_guarda_el_id_de_hcvet_y_envia_nombres_legales():
    repo, u = preparar()
    hcvet = vincular(repo, u)
    cuerpo = hcvet.cuerpos("POST", "/propietarios")[0]
    assert cuerpo["propietario"] == {
        "dni": DNI, "nombres": "ANA MARIA", "apellidos": "PEREZ ROJAS", "distrito": "Miraflores",
        "telefono": "987654321", "email": "ana@example.com",
        "permite_indexacion_veterinaria": True, "permite_uso_comercial": True,
    }
    assert "Anita" not in json.dumps(cuerpo)  # el nombre visible no viaja
    assert cuerpo["alcances"] == list(c.ALCANCES_PAKU) and "propietario.registrar" in cuerpo["alcances"]
    assert cuerpo["version_terminos"] == c.VERSION_TEXTOS
    assert {x["tipo"] for x in cuerpo["consentimientos"]} == {c.HISTORIAL, c.REGISTRO_EVENTOS}
    assert "password" not in json.dumps(cuerpo)
    alta = repo.de(u.id, s.ALTA)[0]
    assert hcvet.solicitudes[0].headers["Idempotency-Key"] == alta.clave_idempotencia
    vinculo = repo.vinculos[u.id]
    assert (vinculo.hcvet_propietario_id, vinculo.hcvet_autorizacion_id, vinculo.dni_vinculado) == (77, 501, DNI)
    assert (alta.estado, alta.id_externo, alta.intentos) == (s.SINCRONIZADO, "77", 1)
    assert correr(servicio(repo).estado(u.id))["integracion"]["estado"] == "vinculado"


def _vincular_basico(reloj=None):
    repo, u = preparar()
    hcvet = HcvetSimulado({
        ("POST", "/propietarios"): CONFLICTO_DNI,
        ("POST", f"/propietarios/{DNI}/autorizaciones"): VINCULO_BASICO,
    })
    correr(procesador(repo, hcvet, reloj).procesar())
    return repo, u, hcvet


def test_dni_existente_se_vincula_con_acceso_basico_sin_duplicar_ni_tocar_sus_consentimientos():
    repo, u, hcvet = _vincular_basico()
    vinculo = repo.vinculos[u.id]
    assert (vinculo.estado, vinculo.acceso, vinculo.hcvet_autorizacion_id, vinculo.hcvet_propietario_id) == (
        s.VINCULADO, s.ACCESO_BASICO, 900, 55)
    assert len(hcvet.cuerpos("POST", "/propietarios")) == 1
    autorizacion = hcvet.cuerpos("POST", f"/propietarios/{DNI}/autorizaciones")[0]
    assert set(autorizacion) == {"alcances", "version_terminos"}  # sin evidencia
    assert repo.de(u.id, s.CONSENTIMIENTO) == []  # no cambia los consentimientos de un propietario que ya existía
    [revision] = repo.de(u.id, s.REVISION_ACCESO)
    assert revision.proximo_intento_en == AHORA + timedelta(hours=s.REVISION_ACCESO_HORAS)
    estado = correr(servicio(repo).estado(u.id))
    assert (estado["integracion"]["estado"], estado["integracion"]["acceso"]) == ("vinculado", "basico")
    assert estado["operaciones_pendientes"] == 0  # la revisión periódica no es un cambio pendiente del cliente


def test_con_acceso_basico_no_se_envian_datos_ni_consentimientos():
    repo, u, _ = _vincular_basico()
    correr(servicio(repo).notificar_cambio_perfil(u.id, {"telefono"}))
    correr(servicio(repo).decidir(u.id, [c.Decision(c.HISTORIAL, False, c.VERSION_TEXTOS)], canal="app", ip=None,
                                  user_agent=None))
    assert repo.de(u.id, s.ACTUALIZACION) == [] and repo.de(u.id, s.CONSENTIMIENTO) == []


def test_la_revision_detecta_cuando_el_dueno_amplia_el_acceso_desde_hcvet():
    reloj = Reloj()
    repo, u, _ = _vincular_basico(reloj)
    reloj.avanzar(hours=s.REVISION_ACCESO_HORAS)
    sigue_basico = HcvetSimulado({("GET", f"/propietarios/{DNI}/autorizaciones"): httpx.Response(200, json=[
        {"id": 900, "acceso": "basico", "vigente": True}])})
    correr(procesador(repo, sigue_basico, reloj).procesar())
    revision = repo.de(u.id, s.REVISION_ACCESO)[0]
    assert (revision.estado, revision.intentos) == (s.PENDIENTE, 0)
    assert repo.vinculos[u.id].acceso == s.ACCESO_BASICO

    reloj.avanzar(hours=s.REVISION_ACCESO_HORAS)
    ampliado = HcvetSimulado({("GET", f"/propietarios/{DNI}/autorizaciones"): httpx.Response(200, json=[
        {"id": 900, "acceso": "basico", "vigente": False}, {"id": 901, "acceso": "completo", "vigente": True}])})
    correr(procesador(repo, ampliado, reloj).procesar())
    vinculo = repo.vinculos[u.id]
    assert (vinculo.acceso, vinculo.hcvet_autorizacion_id) == (s.ACCESO_COMPLETO, 901)
    assert revision.estado == s.SINCRONIZADO
    # Ahora sí se registran en HCVet las decisiones que el cliente tomó en Paku.
    assert sorted(op.payload["tipo"] for op in repo.de(u.id, s.CONSENTIMIENTO)) == sorted(c.TIPOS_HCVET)


def test_la_revision_detecta_que_el_dueno_revoco_a_paku():
    reloj = Reloj()
    repo, u, _ = _vincular_basico(reloj)
    reloj.avanzar(hours=s.REVISION_ACCESO_HORAS)
    revocado = HcvetSimulado({("GET", f"/propietarios/{DNI}/autorizaciones"): httpx.Response(200, json=[
        {"id": 900, "acceso": "basico", "vigente": False}])})
    correr(procesador(repo, revocado, reloj).procesar())
    assert (repo.vinculos[u.id].estado, repo.vinculos[u.id].motivo) == (s.VINCULO_FALLIDO, s.AUTORIZACION_NO_VIGENTE)


def test_vinculacion_recupera_la_autorizacion_creada_en_un_intento_sin_respuesta():
    repo, u = preparar()
    hcvet = HcvetSimulado({
        ("POST", "/propietarios"): CONFLICTO_DNI,
        ("POST", f"/propietarios/{DNI}/autorizaciones"): httpx.Response(409, json={"detail": "Ya vigente"}),
        ("GET", f"/propietarios/{DNI}/autorizaciones"): httpx.Response(200, json=[
            {"id": 10, "vigente": False}, {"id": 11, "propietario_id": 55, "acceso": "basico", "vigente": True}]),
    })
    correr(procesador(repo, hcvet).procesar())
    assert (repo.vinculos[u.id].hcvet_autorizacion_id, repo.vinculos[u.id].acceso) == (11, s.ACCESO_BASICO)


def test_vinculacion_rechazada_queda_en_conflicto_sin_reintentar():
    repo, u = preparar()
    hcvet = HcvetSimulado({
        ("POST", "/propietarios"): CONFLICTO_DNI,
        ("POST", f"/propietarios/{DNI}/autorizaciones"): httpx.Response(409, json={"detail": "Evidencia insuficiente"}),
        ("GET", f"/propietarios/{DNI}/autorizaciones"): httpx.Response(404, json={"detail": "No existe"}),
    })
    reloj = Reloj()
    correr(procesador(repo, hcvet, reloj).procesar())
    alta = repo.de(u.id, s.ALTA)[0]
    assert alta.estado in (s.CONFLICTO, s.FALLIDO) and not alta.reintentable
    assert repo.vinculos[u.id].estado in (s.VINCULO_CONFLICTO, s.VINCULO_FALLIDO)
    antes = len(hcvet.solicitudes)
    reloj.avanzar(days=1)
    correr(procesador(repo, hcvet, reloj).procesar())
    assert len(hcvet.solicitudes) == antes


# --- Reintentos e idempotencia ---


def test_falla_temporal_reintenta_con_espera_y_la_misma_clave():
    repo, u = preparar()
    hcvet = HcvetSimulado({("POST", "/propietarios"): [httpx.Response(503), ALTA_OK]})
    reloj = Reloj()
    correr(procesador(repo, hcvet, reloj).procesar())
    alta = repo.de(u.id, s.ALTA)[0]
    assert (alta.estado, alta.reintentable, alta.motivo) == (s.FALLIDO, True, s.HCVET_NO_DISPONIBLE)
    assert alta.proximo_intento_en == AHORA + timedelta(minutes=1)
    assert correr(servicio(repo).estado(u.id))["integracion"]["estado"] == "pendiente"  # nunca "vinculado"

    correr(procesador(repo, hcvet, reloj).procesar())  # todavía no toca
    assert len(hcvet.solicitudes) == 1
    reloj.avanzar(minutes=2)
    correr(procesador(repo, hcvet, reloj).procesar())
    claves = {r.headers["Idempotency-Key"] for r in hcvet.solicitudes}
    assert len(hcvet.solicitudes) == 2 and claves == {alta.clave_idempotencia}
    assert repo.vinculos[u.id].estado == s.VINCULADO


def test_429_respeta_retry_after():
    repo, u = preparar()
    hcvet = HcvetSimulado({("POST", "/propietarios"): httpx.Response(429, headers={"Retry-After": "900"})})
    correr(procesador(repo, hcvet).procesar())
    assert repo.de(u.id, s.ALTA)[0].proximo_intento_en == AHORA + timedelta(seconds=900)


def test_reintentos_agotados_dejan_la_operacion_fallida():
    repo, u = preparar()
    hcvet = HcvetSimulado({("POST", "/propietarios"): httpx.Response(502)})
    reloj = Reloj()
    for _ in range(s.MAX_INTENTOS + 2):
        correr(procesador(repo, hcvet, reloj).procesar())
        reloj.avanzar(hours=5)
    alta = repo.de(u.id, s.ALTA)[0]
    assert (alta.estado, alta.motivo, alta.reintentable, alta.intentos) == (
        s.FALLIDO, s.REINTENTOS_AGOTADOS, False, s.MAX_INTENTOS)
    assert len(hcvet.solicitudes) == s.MAX_INTENTOS
    assert repo.vinculos[u.id].estado == s.VINCULO_FALLIDO


@pytest.mark.parametrize("status", [401, 403, 422])
def test_rechazos_de_permisos_o_datos_no_se_reintentan(status):
    repo, u = preparar()
    hcvet = HcvetSimulado({("POST", "/propietarios"): httpx.Response(status, json={"detail": "no"})})
    reloj = Reloj()
    correr(procesador(repo, hcvet, reloj).procesar())
    reloj.avanzar(days=2)
    correr(procesador(repo, hcvet, reloj).procesar())
    alta = repo.de(u.id, s.ALTA)[0]
    assert (alta.estado, alta.reintentable) == (s.FALLIDO, False) and len(hcvet.solicitudes) == 1


def test_un_envio_colgado_se_retoma_con_la_misma_clave():
    repo, u = preparar()
    alta = repo.de(u.id, s.ALTA)[0]
    alta.estado, alta.actualizado_en, alta.intentos = s.SINCRONIZANDO, AHORA - timedelta(minutes=30), 1
    hcvet = HcvetSimulado({("POST", "/propietarios"): ALTA_OK})
    correr(procesador(repo, hcvet).procesar())
    assert alta.estado == s.SINCRONIZADO
    assert hcvet.solicitudes[0].headers["Idempotency-Key"] == alta.clave_idempotencia


def test_operaciones_dependientes_esperan_al_vinculo_sin_gastar_intentos():
    repo, u = preparar()
    espera = HcvetOperacionModel(id=uuid4(), user_id=u.id, entidad="propietario", tipo=s.ACTUALIZACION,
                                 estado=s.PENDIENTE, clave_idempotencia="k-dep", payload={"campos": ["telefono"]},
                                 intentos=0, reintentable=False, creado_en=AHORA, actualizado_en=AHORA)
    repo.ops.append(espera)
    hcvet = HcvetSimulado()
    repo.usuarios[u.id].phone = None  # el alta queda bloqueada por datos incompletos
    correr(procesador(repo, hcvet).procesar())
    assert (espera.estado, espera.motivo, espera.intentos) == (s.PENDIENTE, s.ESPERA_VINCULO, 0)
    assert hcvet.solicitudes == []


def test_admin_puede_reencolar_una_operacion_fallida():
    repo, u = preparar()
    hcvet = HcvetSimulado({("POST", "/propietarios"): [httpx.Response(401, json={"detail": "x"}), ALTA_OK]})
    correr(procesador(repo, hcvet).procesar())
    alta = repo.de(u.id, s.ALTA)[0]
    assert alta.estado == s.FALLIDO
    correr(procesador(repo, hcvet).reintentar(alta.id))
    assert (alta.estado, alta.intentos) == (s.PENDIENTE, 0)
    correr(procesador(repo, hcvet).procesar())
    assert alta.estado == s.SINCRONIZADO


# --- Consentimientos y revocación con el propietario vinculado ---


def test_cambio_de_consentimiento_vinculado_se_envia_a_hcvet():
    repo, u = preparar()
    vincular(repo, u)
    correr(servicio(repo).decidir(u.id, [c.Decision(c.HISTORIAL, False, c.VERSION_TEXTOS)], canal="app", ip=None,
                                  user_agent=None))
    hcvet = HcvetSimulado({("PUT", f"/propietarios/{DNI}/consentimientos/{c.HISTORIAL}"): httpx.Response(200, json={})})
    correr(procesador(repo, hcvet).procesar())
    assert hcvet.cuerpos("PUT", f"/propietarios/{DNI}/consentimientos/{c.HISTORIAL}") == [
        {"concedido": False, "finalidad": c.TEXTOS[c.HISTORIAL].finalidad, "version_texto": c.VERSION_TEXTOS}]


def test_revocar_la_integracion_revoca_la_autorizacion_sin_borrar_datos():
    repo, u = preparar()
    vincular(repo, u)
    correr(servicio(repo).notificar_cambio_perfil(u.id, {"telefono"}))
    correr(servicio(repo).decidir(
        u.id, [c.Decision(c.REGISTRO_EVENTOS, False, c.VERSION_TEXTOS), c.Decision(c.INTEGRACION, False,
                                                                                    c.VERSION_TEXTOS)],
        canal="web", ip=None, user_agent=None))
    assert repo.de(u.id, s.ACTUALIZACION)[0].estado == s.CANCELADO
    hcvet = HcvetSimulado({
        ("PUT", f"/propietarios/{DNI}/consentimientos/{c.REGISTRO_EVENTOS}"): httpx.Response(200, json={}),
        ("DELETE", f"/propietarios/{DNI}/autorizaciones/501"): httpx.Response(204),
    })
    correr(procesador(repo, hcvet).procesar())
    assert [r.method for r in hcvet.solicitudes] == ["PUT", "DELETE"]  # consentimiento antes de perder el acceso
    assert repo.vinculos[u.id].estado == s.VINCULO_REVOCADO
    assert repo.vinculos[u.id].hcvet_propietario_id == 77  # la referencia se conserva


def test_volver_a_autorizar_tras_revocar_vincula_de_nuevo():
    repo, u = preparar()
    vincular(repo, u)
    correr(servicio(repo).decidir(u.id, [c.Decision(c.INTEGRACION, False, c.VERSION_TEXTOS)], canal="web", ip=None,
                                  user_agent=None))
    correr(servicio(repo).decidir(u.id, [c.Decision(c.INTEGRACION, True, c.VERSION_TEXTOS)], canal="web", ip=None,
                                  user_agent=None))
    altas = repo.de(u.id, s.ALTA)
    assert len(altas) == 2 and altas[1].clave_idempotencia != altas[0].clave_idempotencia


# --- Actualización controlada de datos básicos ---


def test_cambios_de_perfil_solo_se_encolan_con_el_propietario_vinculado_y_se_agrupan():
    repo, u = preparar()
    correr(servicio(repo).notificar_cambio_perfil(u.id, {"telefono"}))
    assert repo.de(u.id, s.ACTUALIZACION) == []  # el alta llevará los datos vigentes
    vincular(repo, u)
    correr(servicio(repo).notificar_cambio_perfil(u.id, {"telefono"}))
    correr(servicio(repo).notificar_cambio_perfil(u.id, {"nombres", "first_name"}))
    ops = repo.de(u.id, s.ACTUALIZACION)
    assert len(ops) == 1 and ops[0].payload == {"campos": ["nombres", "telefono"]}


def test_actualizacion_envia_datos_al_y_verificacion_de_nombres_y_respeta_el_409():
    repo, u = preparar()
    vincular(repo, u)
    u.phone, u.updated_at = "912-345-678", AHORA
    correr(servicio(repo).notificar_cambio_perfil(u.id, {"telefono", "nombres"}))
    hcvet = HcvetSimulado({("PATCH", f"/propietarios/{DNI}"): httpx.Response(
        409, json={"detail": "telefono: HCVet tiene un dato más reciente (987654321)."})})
    correr(procesador(repo, hcvet).procesar())
    cuerpo = hcvet.cuerpos("PATCH", f"/propietarios/{DNI}")[0]
    assert cuerpo["telefono"] == "912345678" and cuerpo["nombres"] == "ANA MARIA"
    assert datetime.fromisoformat(cuerpo["datos_al"]) == AHORA
    assert cuerpo["verificaciones"] == {"nombres": {"metodo": "consulta_datos_peru", "fecha": "2026-11-27",
                                                    "referencia": "paku:consulta-dni"}}
    assert "Anita" not in json.dumps(cuerpo)
    op = repo.de(u.id, s.ACTUALIZACION)[0]
    assert (op.estado, op.reintentable) == (s.CONFLICTO, False)
    assert "987654321" not in (op.ultimo_error or "")
    assert repo.vinculos[u.id].estado == s.VINCULADO  # un conflicto de datos no rompe el vínculo


def test_campos_cambiados_ignoran_formato_y_nombre_visible():
    legales = DatosLegales("ANA", "PEREZ", "datosperu", AHORA)
    antes = SimpleNamespace(phone="987 654 321", datos_legales=legales, first_name="Ana")
    assert campos_cambiados_para_hcvet(antes, SimpleNamespace(phone="987-654-321", datos_legales=legales,
                                                              first_name="Anita")) == set()
    otros = DatosLegales("ANA", "PEREZ ROJAS", "datosperu", AHORA)
    assert campos_cambiados_para_hcvet(antes, SimpleNamespace(phone="999888777", datos_legales=otros)) == {
        "telefono", "apellidos"}


def test_con_el_propietario_vinculado_el_dni_queda_bloqueado():
    repo, u = preparar()
    assert correr(servicio(repo).dni_bloqueado(u.id)) is False
    vincular(repo, u)
    assert correr(servicio(repo).dni_bloqueado(u.id)) is True


# --- HTTP ---


def _app_http(repo, current: CurrentUser | None):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.auth import get_current_user
    from app.modules.hcvet.api import router as hcvet_router

    app = FastAPI()
    app.include_router(hcvet_router.router)
    app.include_router(hcvet_router.admin_router, prefix="/admin")
    app.dependency_overrides[hcvet_router.obtener_repositorio_hcvet] = lambda: repo
    if current is not None:
        app.dependency_overrides[get_current_user] = lambda: current
    return TestClient(app)


def _sesion(u, role="user"):
    return CurrentUser(id=u.id, email=u.email, role=role, is_active=True)


def test_http_exige_sesion_de_cliente():
    repo = RepoFalso()
    u = repo.agregar_usuario(usuario())
    assert _app_http(repo, None).get("/users/me/hcvet").status_code in (401, 403)
    respuesta = _app_http(repo, _sesion(u, "groomer")).get("/users/me/hcvet")
    assert respuesta.status_code == 403 and respuesta.json()["detail"]["code"] == "HCVET_ONLY_CLIENTS"


def test_http_registra_decisiones_con_ip_y_canal():
    repo = RepoFalso()
    u = repo.agregar_usuario(usuario())
    cliente = _app_http(repo, _sesion(u))
    respuesta = cliente.put("/users/me/hcvet/consentimientos", headers={"X-Forwarded-For": "200.1.2.3, 10.0.0.1"},
                            json={"canal": "app", "decisiones": [
                                {"tipo": c.INTEGRACION, "concedido": True, "version_texto": c.VERSION_TEXTOS}]})
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["integracion"]["estado"] == "pendiente" and cuerpo["operaciones_pendientes"] == 1
    assert repo.filas[0].ip == "200.1.2.3" and repo.filas[0].canal == "app"


def test_http_texto_desactualizado_y_concedido_obligatorio():
    repo = RepoFalso()
    u = repo.agregar_usuario(usuario())
    cliente = _app_http(repo, _sesion(u))
    viejo = cliente.put("/users/me/hcvet/consentimientos", json={"canal": "web", "decisiones": [
        {"tipo": c.INTEGRACION, "concedido": True, "version_texto": "v0"}]})
    assert viejo.status_code == 409 and viejo.json()["detail"]["code"] == "CONSENT_TEXT_OUTDATED"
    sin_decidir = cliente.put("/users/me/hcvet/consentimientos", json={"canal": "web", "decisiones": [
        {"tipo": c.INTEGRACION, "version_texto": c.VERSION_TEXTOS}]})
    assert sin_decidir.status_code == 422
    assert repo.filas == []


def test_http_admin_lista_la_cola_sin_datos_personales():
    repo, u = preparar()
    respuesta = _app_http(repo, _sesion(u, "admin")).get("/admin/hcvet/operaciones")
    assert respuesta.status_code == 200
    texto = respuesta.text
    assert DNI not in texto and "ana@example.com" not in texto
    assert respuesta.json()[0]["tipo"] == s.ALTA
    assert _app_http(repo, _sesion(u)).get("/admin/hcvet/operaciones").status_code == 403


# --- Migración ---


def test_migracion_crea_las_tres_tablas_y_sigue_al_indice_de_dni():
    texto = (Path(__file__).resolve().parents[2] / "alembic" / "versions" / "f4b2c8e1a7d3_hcvet_integracion.py"
             ).read_text(encoding="utf-8")
    assert 'down_revision: Union[str, None] = "e8f3a1c7d5b2"' in texto
    for tabla in ("hcvet_consentimientos", "hcvet_vinculos", "hcvet_operaciones"):
        assert f'op.create_table(\n        "{tabla}"' in texto and f'op.drop_table("{tabla}")' in texto
    assert "uq_hcvet_operaciones_alta_abierta" in texto and "uq_hcvet_vinculos_propietario" in texto
    assert not re.search(r"\b(DELETE|UPDATE)\b", texto)


# --- «Mi perfil» (PUT /users/me) con el propietario vinculado ---


def _perfil_http(usuario_iam, repo_hcvet):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.modules.hcvet.api.router import obtener_repositorio_hcvet
    from app.modules.iam.api import router as iam_router
    from tests.unit.test_registro_con_dni import _Repo

    app = FastAPI()
    app.include_router(iam_router.router)
    app.dependency_overrides[iam_router.get_current_user_db] = lambda: CurrentUser(
        id=usuario_iam.id, email=usuario_iam.email, role="user", is_active=True)
    app.dependency_overrides[iam_router.get_user_repo] = lambda: _Repo(usuario_iam)
    app.dependency_overrides[obtener_repositorio_hcvet] = lambda: repo_hcvet
    return TestClient(app)


def _cliente_iam_vinculado():
    from tests.unit.test_registro_con_dni import _cliente

    cliente = _cliente(dni=DNI)
    repo = RepoFalso()
    u = repo.agregar_usuario(usuario(id=cliente.id))
    correr(servicio(repo).decidir(u.id, TODO_CONCEDIDO, canal="web", ip=None, user_agent=None))
    vincular(repo, u)
    return cliente, repo


def test_mi_perfil_no_cambia_el_dni_vinculado_a_hcvet():
    cliente, repo = _cliente_iam_vinculado()
    respuesta = _perfil_http(cliente, repo).put("/users/me", json={"dni": "11223344"})
    assert respuesta.status_code == 409 and respuesta.json()["detail"]["code"] == "DNI_LOCKED_BY_HCVET"
    assert _perfil_http(cliente, repo).put("/users/me", json={"dni": DNI}).status_code == 200  # el mismo sí


def test_mi_perfil_encola_el_telefono_para_hcvet_sin_llamarlo():
    cliente, repo = _cliente_iam_vinculado()
    respuesta = _perfil_http(cliente, repo).put("/users/me", json={"phone": "955444333", "first_name": "Anny"})
    assert respuesta.status_code == 200
    ops = repo.de(cliente.id, s.ACTUALIZACION)
    assert len(ops) == 1 and ops[0].payload == {"campos": ["telefono"]}  # el nombre visible no se notifica
