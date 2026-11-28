"""Consulta de DNI contra Datos Perú y nombres legales (feature 0027, PAKU-USERS-007).

Integración con respuestas simuladas (``httpx.MockTransport``): ninguna prueba llama a Datos Perú ni consume consultas
reales. La clave usada es sintética.
"""

import asyncio
import json
import logging
from datetime import date
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from app.core.auth import CurrentUser
from app.core.settings import settings
from app.modules.iam.api import router as iam_router
from app.modules.iam.api.schemas import CompleteProfileIn, DniConsultaIn, UpdateProfileIn
from app.modules.iam.app.use_cases_impl.profile import CompleteProfile, RegisterUser, UpdateProfile
from app.modules.iam.domain.dni import ConsultaDniLimitada, ConsultaDniNoDisponible, DniNoEncontrado
from app.modules.iam.domain.user import Sex, User
from app.modules.iam.infra.consultor_dni import (
    ConsultorDniDatosPeru,
    ConsultorDniNoDisponible,
    obtener_consultor_dni,
)

DNI = "44556677"
URL = "https://datosperu.prueba"
CLAVE = "dp_pru_clave_sintetica_de_prueba"
OFICIAL = {"dni": DNI, "nombres": "ANA MARÍA", "apellidos": "PÉREZ ROJAS"}


class _DatosPeruSimulado:
    """Datos Perú simulado: registra cada solicitud y responde lo configurado."""

    def __init__(self, estado: int = 200, cuerpo=None, error: Exception | None = None) -> None:
        self.estado = estado
        self.cuerpo = OFICIAL if cuerpo is None else cuerpo
        self.error = error
        self.solicitudes: list[httpx.Request] = []

    def __call__(self, solicitud: httpx.Request) -> httpx.Response:
        self.solicitudes.append(solicitud)
        if self.error is not None:
            raise self.error
        if isinstance(self.cuerpo, str):
            return httpx.Response(self.estado, text=self.cuerpo)
        return httpx.Response(self.estado, json=self.cuerpo)

    def consultor(self) -> ConsultorDniDatosPeru:
        return ConsultorDniDatosPeru(url=URL, api_key=CLAVE, timeout=2, transport=httpx.MockTransport(self))


class _Repo:
    def __init__(self, *usuarios: User) -> None:
        self.usuarios = {u.id: u for u in usuarios}

    async def get_by_email(self, email):
        return next((u for u in self.usuarios.values() if u.email == email.lower()), None)

    async def get_by_dni(self, dni):
        return next((u for u in self.usuarios.values() if u.dni == dni), None)

    async def get_by_id(self, user_id):
        return self.usuarios.get(user_id)

    async def add(self, user):
        self.usuarios[user.id] = user

    async def update(self, user):
        self.usuarios[user.id] = user


@pytest.fixture(autouse=True)
def consulta_limpia():
    iam_router.LIMITES_CONSULTA_DNI.reiniciar()
    iam_router.CACHE_DNI.reiniciar()


def _token(usuario: User) -> CurrentUser:
    return CurrentUser(id=usuario.id, email=usuario.email, role=usuario.role, is_active=True, profile_completed=True)


def _consultar(usuario: User, consultor, dni: str = DNI):
    return asyncio.run(iam_router.consultar_dni(DniConsultaIn(dni=dni), current=_token(usuario), consultor=consultor))


# --- Adaptador ---


def test_el_adaptador_llama_a_datos_peru_con_la_clave_de_cliente_y_solo_el_dni():
    datosperu = _DatosPeruSimulado()
    datos = asyncio.run(datosperu.consultor().consultar(DNI))

    assert (datos.nombres, datos.apellidos, datos.fuente) == ("ANA MARÍA", "PÉREZ ROJAS", "datosperu")
    [solicitud] = datosperu.solicitudes
    assert solicitud.method == "POST" and str(solicitud.url) == f"{URL}/v1/dni/consulta"
    assert solicitud.headers["Authorization"] == f"Bearer {CLAVE}"
    assert json.loads(solicitud.content) == {"dni": DNI}  # Paku no elige proveedor


def test_dni_inexistente_es_no_encontrado():
    with pytest.raises(DniNoEncontrado):
        asyncio.run(_DatosPeruSimulado(estado=404, cuerpo={"error": {}}).consultor().consultar(DNI))


@pytest.mark.parametrize("estado", [401, 403, 422, 500, 502, 503])
def test_otros_estados_son_no_disponible_sin_reintentos(estado):
    datosperu = _DatosPeruSimulado(estado=estado, cuerpo={"error": {"codigo": "x"}})
    with pytest.raises(ConsultaDniNoDisponible):
        asyncio.run(datosperu.consultor().consultar(DNI))
    assert len(datosperu.solicitudes) == 1


@pytest.mark.parametrize("error", [httpx.ConnectTimeout("t"), httpx.ReadTimeout("t"), httpx.ConnectError("c")])
def test_timeout_o_red_caida_es_no_disponible(error):
    datosperu = _DatosPeruSimulado(error=error)
    with pytest.raises(ConsultaDniNoDisponible):
        asyncio.run(datosperu.consultor().consultar(DNI))
    assert len(datosperu.solicitudes) == 1


@pytest.mark.parametrize("cuerpo", ["no es json", {"dni": DNI}, {"dni": DNI, "nombres": "", "apellidos": "X"}, [1]])
def test_respuesta_con_forma_inesperada_es_no_disponible(cuerpo):
    with pytest.raises(ConsultaDniNoDisponible):
        asyncio.run(_DatosPeruSimulado(cuerpo=cuerpo).consultor().consultar(DNI))


def test_los_logs_no_contienen_la_clave_ni_el_dni(caplog):
    caplog.set_level(logging.DEBUG)
    for simulado in (_DatosPeruSimulado(estado=500), _DatosPeruSimulado(error=httpx.ConnectTimeout(CLAVE + DNI))):
        with pytest.raises(ConsultaDniNoDisponible) as fallo:
            asyncio.run(simulado.consultor().consultar(DNI))
        assert CLAVE not in str(fallo.value) and DNI not in str(fallo.value)
    assert CLAVE not in caplog.text and DNI not in caplog.text


def test_la_configuracion_elige_el_adaptador(monkeypatch):
    monkeypatch.setattr(settings, "DATOSPERU_URL", "")
    monkeypatch.setattr(settings, "DATOSPERU_API_KEY", CLAVE)
    assert isinstance(obtener_consultor_dni(), ConsultorDniNoDisponible)

    monkeypatch.setattr(settings, "DATOSPERU_URL", URL)
    monkeypatch.setattr(settings, "DATOSPERU_API_KEY", "")
    assert isinstance(obtener_consultor_dni(), ConsultorDniNoDisponible)

    monkeypatch.setattr(settings, "DATOSPERU_API_KEY", CLAVE)
    assert isinstance(obtener_consultor_dni(), ConsultorDniDatosPeru)


# --- Ruta con Datos Perú simulado ---


def _cliente_correo() -> User:
    return User.new(
        email="luis@example.com", password_hash="x", phone="999111222", first_name="Lucho", last_name="R.",
        sex=Sex.male, birth_date=date(1992, 5, 5),
    )


def test_la_ruta_responde_con_datos_peru_y_usa_la_cache():
    datosperu = _DatosPeruSimulado()
    usuario = _cliente_correo()
    assert _consultar(usuario, datosperu.consultor()).model_dump() == OFICIAL
    assert _consultar(usuario, datosperu.consultor()).model_dump() == OFICIAL
    assert len(datosperu.solicitudes) == 1  # la segunda sale de la caché


@pytest.mark.parametrize("estado, codigo", [(404, 404), (503, 503), (401, 503)])
def test_la_ruta_traduce_las_respuestas_de_datos_peru(estado, codigo):
    with pytest.raises(HTTPException) as fallo:
        _consultar(_cliente_correo(), _DatosPeruSimulado(estado=estado, cuerpo={"error": {}}).consultor())
    assert fallo.value.status_code == codigo


# --- Nombres legales en el completado de perfil de todos los métodos de registro ---


def test_registro_con_correo_y_completado_en_mi_perfil_guarda_los_nombres_legales():
    repo = _Repo()
    usuario = asyncio.run(RegisterUser(repo=repo, buscar_datos_oficiales=iam_router.buscar_datos_oficiales).execute(
        email="luis@example.com", password="Clave123", phone="999111222", first_name="Lucho", last_name="R.",
        sex=Sex.male, birth_date=date(1992, 5, 5),
    ))
    assert usuario.datos_legales is None

    _consultar(usuario, _DatosPeruSimulado().consultor())  # ya con sesión, en «Mi perfil»
    actualizado = asyncio.run(
        UpdateProfile(repo=repo, buscar_datos_oficiales=iam_router.buscar_datos_oficiales).execute(usuario.id, dni=DNI)
    )

    legales = actualizado.datos_legales
    assert (legales.nombres, legales.apellidos, legales.fuente) == ("ANA MARÍA", "PÉREZ ROJAS", "datosperu")
    assert (actualizado.first_name, actualizado.last_name) == ("Lucho", "R.")  # el nombre visible no cambia


def test_completado_de_perfil_social_guarda_los_nombres_legales():
    social = User.new_social(email="ana@gmail.com", first_name="Anita", last_name="P")
    repo = _Repo(social)
    _consultar(social, _DatosPeruSimulado().consultor())
    completo = asyncio.run(
        CompleteProfile(repo=repo, buscar_datos_oficiales=iam_router.buscar_datos_oficiales).execute(
            social.id, phone="999888777", sex=Sex.female, birth_date=date(1990, 1, 1), dni=DNI
        )
    )
    assert completo.datos_legales.nombres == "ANA MARÍA" and completo.first_name == "Anita"


def test_sin_consulta_previa_no_hay_nombres_legales():
    usuario = _cliente_correo()
    repo = _Repo(usuario)
    actualizado = asyncio.run(
        UpdateProfile(repo=repo, buscar_datos_oficiales=iam_router.buscar_datos_oficiales).execute(usuario.id, dni=DNI)
    )
    assert actualizado.dni == DNI and actualizado.datos_legales is None


def test_cambiar_el_dni_sin_consultarlo_borra_los_nombres_legales_y_mantenerlo_los_conserva():
    usuario = _cliente_correo()
    repo = _Repo(usuario)
    actualizar = UpdateProfile(repo=repo, buscar_datos_oficiales=iam_router.buscar_datos_oficiales)
    _consultar(usuario, _DatosPeruSimulado().consultor())
    asyncio.run(actualizar.execute(usuario.id, dni=DNI))
    iam_router.CACHE_DNI.reiniciar()

    asyncio.run(actualizar.execute(usuario.id, phone="999000111"))  # mismo DNI
    assert repo.usuarios[usuario.id].datos_legales is not None

    asyncio.run(actualizar.execute(usuario.id, dni="11223344"))  # otro DNI, sin consulta
    assert repo.usuarios[usuario.id].datos_legales is None


@pytest.mark.parametrize("modelo", [UpdateProfileIn, CompleteProfileIn])
def test_el_cliente_no_puede_enviar_nombres_legales(modelo):
    assert not {"legal_first_name", "legal_last_name", "legal_data_source"} & set(modelo.model_fields)


def test_user_out_expone_los_nombres_legales():
    usuario = _cliente_correo()
    repo = _Repo(usuario)
    _consultar(usuario, _DatosPeruSimulado().consultor())
    actualizado = asyncio.run(
        UpdateProfile(repo=repo, buscar_datos_oficiales=iam_router.buscar_datos_oficiales).execute(usuario.id, dni=DNI)
    )
    salida = iam_router._user_to_out(actualizado)
    assert (salida.legal_first_name, salida.legal_last_name, salida.legal_data_source) == (
        "ANA MARÍA", "PÉREZ ROJAS", "datosperu")
    assert salida.legal_data_checked_at is not None
    assert (salida.first_name, salida.last_name) == ("Lucho", "R.")

    sin_legales = iam_router._user_to_out(_cliente_correo())
    assert sin_legales.legal_first_name is None and sin_legales.legal_data_checked_at is None


def test_el_repositorio_guarda_y_lee_los_nombres_legales_sin_base():
    from dataclasses import replace
    from datetime import datetime, timezone

    from app.modules.iam.domain.user import DatosLegales
    from app.modules.iam.infra.models import UserModel
    from app.modules.iam.infra.postgres_user_repository import _datos_legales, _escribir_datos_legales

    legales = DatosLegales("ANA MARÍA", "PÉREZ ROJAS", "datosperu", datetime(2026, 11, 28, tzinfo=timezone.utc))
    modelo = UserModel()
    _escribir_datos_legales(modelo, replace(_cliente_correo(), datos_legales=legales).datos_legales)
    assert (modelo.legal_first_name, modelo.legal_data_source) == ("ANA MARÍA", "datosperu")
    assert _datos_legales(modelo) == legales

    _escribir_datos_legales(modelo, None)
    assert modelo.legal_first_name is None and _datos_legales(modelo) is None


# --- 429 de Datos Perú: se conserva Retry-After ---


class _DatosPeruLimitado(_DatosPeruSimulado):
    def __init__(self, retry_after):
        super().__init__(estado=429, cuerpo={"error": {"codigo": "limite_excedido"}})
        self.retry_after = retry_after

    def __call__(self, solicitud):
        self.solicitudes.append(solicitud)
        cabeceras = {} if self.retry_after is None else {"Retry-After": self.retry_after}
        return httpx.Response(429, json=self.cuerpo, headers=cabeceras)


@pytest.mark.parametrize("cabecera, esperado", [("37", 37), (None, 60), ("pronto", 60), ("0", 1), ("999999", 86400)])
def test_el_429_de_datos_peru_conserva_retry_after(cabecera, esperado):
    datosperu = _DatosPeruLimitado(cabecera)
    with pytest.raises(ConsultaDniLimitada) as fallo:
        asyncio.run(datosperu.consultor().consultar(DNI))
    assert fallo.value.reintentar_en == esperado and len(datosperu.solicitudes) == 1


def test_la_ruta_responde_429_con_el_retry_after_de_datos_peru():
    with pytest.raises(HTTPException) as fallo:
        _consultar(_cliente_correo(), _DatosPeruLimitado("42").consultor())
    assert fallo.value.status_code == 429
    assert fallo.value.headers["Retry-After"] == "42"
    assert fallo.value.detail == {
        "code": "DNI_LOOKUP_RATE_LIMITED",
        "message": "La consulta de DNI está ocupada. Reintenta en 42 segundos.",
        "retry_after": 42,
    }


def test_un_429_de_datos_peru_no_se_guarda_en_cache():
    usuario = _cliente_correo()
    with pytest.raises(HTTPException):
        _consultar(usuario, _DatosPeruLimitado("5").consultor())
    datosperu = _DatosPeruSimulado()
    assert _consultar(usuario, datosperu.consultor()).model_dump() == OFICIAL
    assert len(datosperu.solicitudes) == 1


# --- Onboarding por HTTP: la consulta exige sesión ---


def _app_http(consultor, usuario: User | None):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core.auth import get_current_user
    from app.modules.iam.infra.consultor_dni import obtener_consultor_dni as dependencia_consultor

    app = FastAPI()
    app.include_router(iam_router.router)
    app.dependency_overrides[dependencia_consultor] = lambda: consultor
    if usuario is not None:
        app.dependency_overrides[get_current_user] = lambda: _token(usuario)
    return TestClient(app)


def test_sin_sesion_la_consulta_se_rechaza_y_no_llama_a_datos_peru():
    datosperu = _DatosPeruSimulado()
    respuesta = _app_http(datosperu.consultor(), None).post("/users/me/dni/consulta", json={"dni": DNI})
    assert respuesta.status_code in (401, 403)
    assert datosperu.solicitudes == []


def test_con_la_sesion_recien_creada_la_consulta_funciona_por_http():
    datosperu = _DatosPeruSimulado()
    respuesta = _app_http(datosperu.consultor(), _cliente_correo()).post("/users/me/dni/consulta", json={"dni": DNI})
    assert respuesta.status_code == 200 and respuesta.json() == OFICIAL


def test_el_429_de_datos_peru_llega_al_front_con_retry_after():
    respuesta = _app_http(_DatosPeruLimitado("42").consultor(), _cliente_correo()).post(
        "/users/me/dni/consulta", json={"dni": DNI})
    assert respuesta.status_code == 429
    assert respuesta.headers["Retry-After"] == "42"
    assert respuesta.json()["detail"]["retry_after"] == 42
