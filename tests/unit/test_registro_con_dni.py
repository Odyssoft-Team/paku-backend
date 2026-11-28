"""Feature 0027: registro con DNI (bloque B de la integración Paku–HCVet). Sin base de datos."""
import asyncio
from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core import auth
from app.core.auth import CurrentUser, require_profile_complete
from app.core.settings import settings
from app.modules.iam.api import router as iam_router
from app.modules.iam.api.schemas import CompleteProfileIn, DniConsultaIn, RegisterIn, UpdateProfileIn
from app.modules.iam.app.use_cases_impl.consulta_dni import CacheDni, ConsultarDni, LimiteConsultaDni, LimitesConsultaDni
from app.modules.iam.app.use_cases_impl.profile import CompleteProfile, RegisterUser, UpdateProfile
from app.modules.iam.domain.dni import ConsultaDniNoDisponible, DatosDni, DniNoEncontrado, normalizar_dni
from app.modules.iam.domain.user import Sex, User, campos_faltantes
from app.modules.iam.infra.consultor_dni import ConsultorDniNoDisponible

DNI = "44556677"


class _Repo:
    """Repositorio en memoria con lo que usan los casos de uso."""

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


def _cliente(email: str = "ana@example.com", dni: str | None = None) -> User:
    return User.new(
        email=email, password_hash="x", phone="999888777", first_name="Ana", last_name="Pérez",
        sex=Sex.female, birth_date=date(1990, 1, 1), dni=dni,
    )


def _registrar(repo: _Repo, *, dni: str | None, role: str = "user", email: str = "nuevo@example.com") -> User:
    return asyncio.run(
        RegisterUser(repo=repo).execute(
            email=email, password="Clave123", phone="999111222", first_name="Luis", last_name="Rojas",
            sex=Sex.male, birth_date=date(1992, 5, 5), role=role, dni=dni,
        )
    )


@pytest.fixture
def dni_obligatorio(monkeypatch):
    monkeypatch.setattr(settings, "DNI_OBLIGATORIO", True)


@pytest.fixture(autouse=True)
def consulta_limpia():
    iam_router.LIMITES_CONSULTA_DNI.reiniciar()
    iam_router.CACHE_DNI.reiniciar()


# --- 1. Formato ---


@pytest.mark.parametrize("valor, esperado", [(" 44556677 ", DNI), ("", None), ("   ", None), (None, None)])
def test_normalizar_dni(valor, esperado):
    assert normalizar_dni(valor) == esperado


@pytest.mark.parametrize("valor", ["4455667", "445566778", "4455667A", "44.556.677"])
def test_dni_invalido(valor):
    with pytest.raises(ValueError):
        normalizar_dni(valor)


@pytest.mark.parametrize("modelo", [RegisterIn, UpdateProfileIn, CompleteProfileIn])
def test_los_esquemas_validan_el_formato(modelo):
    base = {
        RegisterIn: {"email": "a@example.com", "password": "Clave123", "phone": "999888777", "first_name": "A",
                     "last_name": "B", "sex": "male", "birth_date": "1990-01-01"},
        UpdateProfileIn: {},
        CompleteProfileIn: {"phone": "999888777", "sex": "male", "birth_date": "1990-01-01"},
    }[modelo]
    with pytest.raises(ValidationError):
        modelo(**base, dni="123")
    assert modelo(**base, dni="").dni is None  # vacío = no enviado (compatibilidad con las apps)
    assert modelo(**base, dni=" 44556677").dni == DNI


# --- 2 y 3. Unicidad ---


def test_registro_con_dni_de_otra_cuenta_es_409_sin_revelarla():
    repo = _Repo(_cliente(dni=DNI))
    with pytest.raises(HTTPException) as error:
        _registrar(repo, dni=DNI)
    assert error.value.status_code == 409 and error.value.detail["code"] == "DNI_ALREADY_REGISTERED"
    assert "ana@example.com" not in str(error.value.detail)
    assert len(repo.usuarios) == 1  # no se creó ni se fusionó


def test_perfil_con_dni_de_otra_cuenta_es_409():
    ana, luis = _cliente(dni=DNI), _cliente(email="luis@example.com")
    repo = _Repo(ana, luis)
    with pytest.raises(HTTPException) as error:
        asyncio.run(UpdateProfile(repo=repo).execute(luis.id, dni=DNI))
    assert error.value.status_code == 409
    assert repo.usuarios[luis.id].dni is None


def test_reenviar_el_propio_dni_no_choca_y_se_puede_cambiar():
    ana = _cliente(dni=DNI)
    repo = _Repo(ana)
    asyncio.run(UpdateProfile(repo=repo).execute(ana.id, dni=DNI))
    asyncio.run(UpdateProfile(repo=repo).execute(ana.id, dni="11223344"))
    assert repo.usuarios[ana.id].dni == "11223344"


# --- 4, 5, 8 y 9. Obligatoriedad ---


def test_con_la_opcion_activa_un_cliente_debe_registrarse_con_dni(dni_obligatorio):
    with pytest.raises(HTTPException) as error:
        _registrar(_Repo(), dni=None)
    assert error.value.status_code == 422 and error.value.detail["code"] == "DNI_REQUIRED"
    assert _registrar(_Repo(), dni=DNI).dni == DNI


def test_con_la_opcion_apagada_el_dni_sigue_siendo_opcional():
    assert settings.DNI_OBLIGATORIO is False  # valor por defecto
    assert _registrar(_Repo(), dni=None).dni is None


@pytest.mark.parametrize("rol", ["groomer", "admin"])
def test_groomers_y_admins_no_necesitan_dni(dni_obligatorio, rol):
    assert _registrar(_Repo(), dni=None, role=rol).role == rol


def test_login_social_completa_el_perfil_con_dni(dni_obligatorio):
    social = User.new_social(email="ana@gmail.com", first_name="Ana", last_name="Pérez")
    repo = _Repo(social)
    completar = CompleteProfile(repo=repo)
    with pytest.raises(HTTPException) as error:
        asyncio.run(completar.execute(social.id, phone="999888777", sex=Sex.female, birth_date=date(1990, 1, 1)))
    assert error.value.detail["code"] == "DNI_REQUIRED"

    asyncio.run(completar.execute(social.id, phone="999888777", sex=Sex.female, birth_date=date(1990, 1, 1), dni=DNI))
    assert repo.usuarios[social.id].profile_completed and repo.usuarios[social.id].dni == DNI


def test_login_social_tambien_valida_la_unicidad():
    social = User.new_social(email="ana@gmail.com", first_name="Ana", last_name="Pérez")
    repo = _Repo(social, _cliente(email="otro@example.com", dni=DNI))
    with pytest.raises(HTTPException) as error:
        asyncio.run(CompleteProfile(repo=repo).execute(
            social.id, phone="999888777", sex=Sex.female, birth_date=date(1990, 1, 1), dni=DNI
        ))
    assert error.value.status_code == 409


# --- 6 y 7. Regularización ---


def test_campos_faltantes_de_un_cliente_existente_sin_dni():
    ana = _cliente()
    assert campos_faltantes(ana, exigir_dni=True) == ["dni"]
    assert campos_faltantes(ana, exigir_dni=False) == []
    assert campos_faltantes(_cliente(dni=DNI), exigir_dni=True) == []


def test_campos_faltantes_de_un_social_nuevo():
    social = User.new_social(email="ana@gmail.com", first_name="Ana", last_name="Pérez")
    assert campos_faltantes(social, exigir_dni=True) == ["phone", "sex", "birth_date", "dni"]


def test_la_respuesta_del_usuario_indica_lo_que_falta(dni_obligatorio, monkeypatch):
    monkeypatch.setattr(iam_router, "to_signed_read_url_or_none", lambda _url: None)
    assert iam_router._user_to_out(_cliente()).missing_profile_fields == ["dni"]


def _cliente_con_token(rol: str = "user") -> CurrentUser:
    return CurrentUser(id=uuid4(), email="ana@example.com", role=rol, is_active=True, profile_completed=True)


def test_sin_dni_no_puede_reservar_y_al_regularizar_si(dni_obligatorio, monkeypatch):
    guard = require_profile_complete()
    tiene_dni = {"valor": False}

    async def dni_en_db(_user_id):
        return tiene_dni["valor"]

    monkeypatch.setattr(auth, "dni_registrado_en_db", dni_en_db)
    with pytest.raises(HTTPException) as error:
        asyncio.run(guard(current=_cliente_con_token()))
    assert error.value.status_code == 403 and error.value.detail["missing_fields"] == ["dni"]

    tiene_dni["valor"] = True  # lo guardó en «Mi perfil»: no necesita volver a iniciar sesión
    assert asyncio.run(guard(current=_cliente_con_token())).role == "user"


def test_el_guard_no_exige_dni_con_la_opcion_apagada_ni_a_groomers(monkeypatch):
    async def sin_dni(_user_id):
        return False

    monkeypatch.setattr(auth, "dni_registrado_en_db", sin_dni)
    guard = require_profile_complete()
    assert asyncio.run(guard(current=_cliente_con_token())).role == "user"
    monkeypatch.setattr(settings, "DNI_OBLIGATORIO", True)
    assert asyncio.run(guard(current=_cliente_con_token("groomer"))).role == "groomer"


# --- 10 a 14. Consulta de DNI ---


class _Reloj:
    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora


class _Consultor:
    def __init__(self, resultado=None, error: Exception | None = None) -> None:
        self.llamadas = 0
        self.resultado = resultado or DatosDni(nombres="ANA MARÍA", apellidos="PÉREZ ROJAS")
        self.error = error

    async def consultar(self, dni):
        self.llamadas += 1
        if self.error:
            raise self.error
        return self.resultado


def test_limite_de_consultas_por_hora():
    reloj = _Reloj()
    limites = LimitesConsultaDni(por_hora=5, distintos_por_dia=100, reloj=reloj)
    usuario = uuid4()
    for _ in range(5):
        limites.registrar(usuario, DNI)
    reloj.ahora += 600
    with pytest.raises(LimiteConsultaDni) as error:
        limites.registrar(usuario, DNI)
    assert error.value.reintentar_en == 3000
    reloj.ahora += 3000
    limites.registrar(usuario, DNI)  # la ventana se desliza


def test_limite_de_dni_distintos_por_dia_y_repetir_no_suma():
    limites = LimitesConsultaDni(por_hora=100, distintos_por_dia=3, reloj=_Reloj())
    usuario = uuid4()
    for dni in ("11111111", "22222222", "33333333", "11111111"):
        limites.registrar(usuario, dni)
    with pytest.raises(LimiteConsultaDni):
        limites.registrar(usuario, "44444444")


def test_los_limites_son_por_usuario():
    limites = LimitesConsultaDni(por_hora=1, distintos_por_dia=1, reloj=_Reloj())
    limites.registrar(uuid4(), DNI)
    limites.registrar(uuid4(), DNI)


def test_la_cache_evita_volver_a_llamar_al_proveedor_y_vence():
    reloj = _Reloj()
    consultor = _Consultor()
    caso = ConsultarDni(
        consultor=consultor,
        limites=LimitesConsultaDni(por_hora=100, distintos_por_dia=100, reloj=reloj),
        cache=CacheDni(duracion=86400, reloj=reloj),
    )
    asyncio.run(caso.execute(uuid4(), DNI))
    asyncio.run(caso.execute(uuid4(), DNI))
    assert consultor.llamadas == 1
    reloj.ahora += 86401
    asyncio.run(caso.execute(uuid4(), DNI))
    assert consultor.llamadas == 2


def test_un_error_no_se_guarda_en_cache():
    consultor = _Consultor(error=ConsultaDniNoDisponible())
    caso = ConsultarDni(consultor=consultor, limites=LimitesConsultaDni(100, 100), cache=CacheDni(duracion=60))
    for _ in range(2):
        with pytest.raises(ConsultaDniNoDisponible):
            asyncio.run(caso.execute(uuid4(), DNI))
    assert consultor.llamadas == 2


def _consultar(consultor, rol: str = "user", current: CurrentUser | None = None):
    current = current or _cliente_con_token(rol)
    return asyncio.run(iam_router.consultar_dni(DniConsultaIn(dni=DNI), current=current, consultor=consultor))


def test_la_ruta_devuelve_solo_nombres_y_apellidos():
    respuesta = _consultar(_Consultor())
    assert respuesta.model_dump() == {"dni": DNI, "nombres": "ANA MARÍA", "apellidos": "PÉREZ ROJAS"}


@pytest.mark.parametrize(
    "error, codigo, clave",
    [(DniNoEncontrado(), 404, "DNI_NOT_FOUND"), (ConsultaDniNoDisponible(), 503, "DNI_LOOKUP_UNAVAILABLE")],
)
def test_la_ruta_traduce_los_errores(error, codigo, clave):
    with pytest.raises(HTTPException) as fallo:
        _consultar(_Consultor(error=error))
    assert fallo.value.status_code == codigo and fallo.value.detail["code"] == clave


def test_la_ruta_responde_429_con_retry_after(monkeypatch):
    monkeypatch.setattr(iam_router, "LIMITES_CONSULTA_DNI", LimitesConsultaDni(por_hora=1, distintos_por_dia=10))
    ana = _cliente_con_token()  # el límite es por usuario: siempre la misma persona
    _consultar(_Consultor(), current=ana)
    with pytest.raises(HTTPException) as fallo:
        _consultar(_Consultor(), current=ana)
    assert fallo.value.status_code == 429 and int(fallo.value.headers["Retry-After"]) >= 1


def test_solo_un_cliente_usa_la_consulta():
    with pytest.raises(HTTPException) as fallo:
        _consultar(_Consultor(), rol="groomer")
    assert fallo.value.status_code == 403


def test_sin_proveedor_configurado_responde_503():
    # Sin DATOSPERU_URL o DATOSPERU_API_KEY: el adaptador por defecto no está disponible.
    with pytest.raises(HTTPException) as fallo:
        _consultar(ConsultorDniNoDisponible())
    assert fallo.value.status_code == 503


def test_la_consulta_exige_el_dni():
    with pytest.raises(ValidationError):
        DniConsultaIn(dni="")
