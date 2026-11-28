"""Índice único de DNI y diagnóstico previo (feature 0027, PAKU-USERS-009). Sin base de datos."""

import asyncio
import importlib.util
from datetime import date
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.modules.iam.app.use_cases_impl.profile import CompleteProfile, RegisterUser, UpdateProfile
from app.modules.iam.domain.user import DniYaRegistrado, Sex, User
from app.modules.iam.infra.postgres_user_repository import es_choque_de_dni
from scripts.diagnostico_dni import FilaUsuario, diagnosticar, enmascarar, formatear

MIGRACION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "e8f3a1c7d5b2_users_dni_unique_index.py"


def _migracion():
    spec = importlib.util.spec_from_file_location("migracion_dni", MIGRACION)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _fila(id_: str, dni: str, role: str = "user") -> FilaUsuario:
    return FilaUsuario(id=id_, role=role, dni=dni, created_at="2026-01-01T00:00:00+00:00")


# --- Diagnóstico ---


def test_diagnostico_sin_problemas_esta_listo():
    informe = diagnosticar([_fila("a", "12345678"), _fila("b", "87654321")])
    assert informe.validos == 2 and informe.listo_para_migrar


def test_diagnostico_clasifica_invalidos_sin_corregirlos():
    informe = diagnosticar([_fila("a", ""), _fila("b", " 12.345.678 "), _fila("c", "1234567"), _fila("d", "X1234567")])
    assert [(h.id, h.categoria) for h in informe.hallazgos] == [
        ("a", "vacio"), ("b", "normalizable"), ("c", "invalido"), ("d", "invalido")]
    assert not informe.listo_para_migrar


def test_diagnostico_detecta_duplicados_incluso_tras_normalizar():
    informe = diagnosticar([_fila("a", "12345678"), _fila("b", "12345678", "groomer"), _fila("c", "12 345 678"),
                            _fila("d", "11112222")])
    [grupo] = informe.duplicados
    assert [u["id"] for u in grupo.usuarios] == ["a", "b", "c"]
    assert grupo.dni_enmascarado == "****5678"


def test_el_informe_no_muestra_dni_completos():
    texto = formatear(diagnosticar([_fila("a", "12345678"), _fila("b", "12345678"), _fila("c", "7654321")]))
    assert "12345678" not in texto and "7654321" not in texto
    assert "****5678" in texto and "No fusionar ni eliminar" in texto


def test_enmascarar():
    assert enmascarar("12345678") == "****5678" and enmascarar("123") == "***"


# --- Migración ---


def test_la_migracion_sigue_a_la_de_nombres_legales_y_crea_indice_parcial_y_check():
    m = _migracion()
    assert (m.revision, m.down_revision) == ("e8f3a1c7d5b2", "d2e7f1a9c4b8")
    fuente = MIGRACION.read_text(encoding="utf-8")
    assert '"uq_users_dni"' in fuente and "unique=True" in fuente and "dni IS NOT NULL" in fuente
    assert '"ck_users_dni_formato"' in fuente
    # No modifica ni borra usuarios
    assert "DELETE" not in fuente.upper().replace("DELETE_", "") and "UPDATE USERS" not in fuente.upper()


@pytest.mark.parametrize("invalidos, duplicados", [(1, 0), (0, 2), (3, 1)])
def test_la_migracion_se_niega_con_datos_invalidos_o_repetidos(invalidos, duplicados):
    with pytest.raises(RuntimeError) as error:
        _migracion().verificar_datos(invalidos, duplicados)
    assert "no modifica, elimina ni fusiona" in str(error.value)


def test_la_migracion_sigue_con_datos_limpios():
    _migracion().verificar_datos(0, 0)


# --- Choque concurrente con el índice: 409, no 500 ---


class _OrigFalso(Exception):
    pass


def test_reconoce_el_choque_con_el_indice_de_dni():
    choque = IntegrityError("INSERT", {}, _OrigFalso('duplicate key value violates unique constraint "uq_users_dni"'))
    otro = IntegrityError("INSERT", {}, _OrigFalso('duplicate key value violates unique constraint "users_email_key"'))
    assert es_choque_de_dni(choque) and not es_choque_de_dni(otro)


class _RepoConIndice:
    """La verificación previa no ve al otro usuario (carrera), pero la base sí lo rechaza."""

    def __init__(self, *usuarios: User) -> None:
        self.usuarios = {u.id: u for u in usuarios}

    async def get_by_email(self, email):
        return None

    async def get_by_dni(self, dni):
        return None

    async def get_by_id(self, user_id):
        return self.usuarios.get(user_id)

    async def add(self, user):
        raise DniYaRegistrado()

    async def update(self, user):
        raise DniYaRegistrado()


def _cliente() -> User:
    return User.new(email="ana@example.com", password_hash="x", phone="999888777", first_name="Ana",
                    last_name="Pérez", sex=Sex.female, birth_date=date(1990, 1, 1))


def test_registro_concurrente_con_el_mismo_dni_responde_409():
    with pytest.raises(HTTPException) as error:
        asyncio.run(RegisterUser(repo=_RepoConIndice()).execute(
            email="luis@example.com", password="Clave123", phone="999111222", first_name="Luis", last_name="R",
            sex=Sex.male, birth_date=date(1992, 5, 5), dni="12345678"))
    assert error.value.status_code == 409 and error.value.detail["code"] == "DNI_ALREADY_REGISTERED"


def test_perfil_y_completado_concurrentes_responden_409():
    ana = _cliente()
    social = User.new_social(email="s@gmail.com", first_name="S", last_name="G")
    repo = _RepoConIndice(ana, social)
    with pytest.raises(HTTPException) as error:
        asyncio.run(UpdateProfile(repo=repo).execute(ana.id, dni="12345678"))
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        asyncio.run(CompleteProfile(repo=repo).execute(
            social.id, phone="999888777", sex=Sex.male, birth_date=date(1990, 1, 1), dni="12345678"))
    assert error.value.status_code == 409
