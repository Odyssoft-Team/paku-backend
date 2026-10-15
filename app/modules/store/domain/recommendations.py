"""Motor de recomendaciones determinístico, sin IA (feature 0008; hojas 17–20 del documento V2).

- Recomienda UN servicio principal por reglas con prioridad (gana el menor número). El cliente puede
  elegir cualquier servicio elegible: la recomendación solo orienta (BR-027). No define el precio, que
  sigue saliendo de la matriz servicio × pelaje × peso.
- Marca cada adicional como recomendado, ofrecido, no disponible o "revisión manual" según preguntas
  codificadas (BR-028), pelaje, peso y servicio.
- Las reglas son DATOS (tabla `recommendation_rules`, versión `PAKU-REC-V1`): se cambian en la base de
  datos sin tocar código. Las preguntas (opciones y cuándo se muestran) son fijas aquí.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

RECOMMENDATION_VERSION = "PAKU-REC-V1"

# Pelaje de la raza (breeds.coat_type) → segmento del documento
SEGMENT_BY_COAT = {
    "simple_short": "S1",
    "simple_medium_long": "S2",
    "curly_no_undercoat": "S3",
    "double_short": "S4",
    "double_long": "S5",
    "mixed_curly_undercoat": "S6",
}

# Acciones (columna "Acción" del documento)
RECOMMEND = "RECOMENDAR"
OFFER = "OFRECER"
UNAVAILABLE = "NO_DISPONIBLE"
REVIEW = "REVISION_MANUAL"
HIDE_SERVICE_ADDONS = "OCULTAR_ADICIONALES_SERVICIO"


@dataclass(frozen=True)
class Question:
    id: str
    variable: str
    text: str
    options: tuple[tuple[str, str], ...]  # (código, texto visible)
    segments: Optional[tuple[str, ...]]   # None = todos
    required: bool


# Hoja 20. Q-SKIN vive en el perfil de la mascota (skin_sensitivity), no se pregunta al reservar.
QUESTIONS: tuple[Question, ...] = (
    Question("Q-SHEDDING", "shedding_level", "¿Está botando mucho más pelo de lo habitual?",
             (("NORMAL", "No / normal"), ("HIGH", "Sí, bastante")), ("S4", "S5"), True),
    Question("Q-MATTING", "matting_level", "¿Cómo está el manto respecto a nudos?",
             (("NONE", "Sin nudos"), ("LOCALIZED", "Algunos puntuales"), ("EXTENDED", "En varias zonas"),
              ("SEVERE", "Muy apelmazado")), ("S2", "S3", "S5", "S6"), True),
    Question("Q-STYLING", "styling_preference", "¿Deseas algún trabajo de corte o styling?",
             (("NONE", "No"), ("RETOUCH", "Retoque carita/patas/cola"), ("FULL_CUT", "Corte completo")),
             ("S2", "S3", "S6"), True),
    Question("Q-TOOTHBRUSH", "owns_toothbrush", "¿Tu mascota ya tiene cepillo dental personal?",
             (("YES", "Sí"), ("NO", "No")), None, False),
)
QUESTIONS_BY_ID = {q.id: q for q in QUESTIONS}


@dataclass(frozen=True)
class Rule:
    id: str
    kind: str                 # "service" | "addon"
    priority: int
    active: bool
    action: str
    conditions: dict          # ver _matches
    target_code: Optional[str] = None   # código del servicio o del adicional
    requires_photo: bool = False
    text: Optional[str] = None
    version: str = RECOMMENDATION_VERSION


@dataclass(frozen=True)
class PetContext:
    age_months: Optional[int]
    weight_kg: Optional[float]
    segment: Optional[str]    # S1..S6; None = sin clasificación (mestizo genérico)
    skin_sensitive: bool


@dataclass
class AddonVerdict:
    code: str
    action: Optional[str] = None      # None = disponible sin recomendación
    rule_id: Optional[str] = None
    text: Optional[str] = None
    requires_photo: bool = False


@dataclass
class AddonEvaluation:
    verdicts: dict[str, AddonVerdict] = field(default_factory=dict)
    review: Optional[Rule] = None      # revisión manual (p. ej. manto muy apelmazado)
    hide_except: Optional[set[str]] = None


def questions_for(segment: Optional[str]) -> list[Question]:
    """Preguntas que aplican a la mascota según su segmento (las de pelaje no aplican sin segmento)."""
    return [q for q in QUESTIONS if q.segments is None or (segment is not None and segment in q.segments)]


def validate_answers(answers: Optional[dict[str, Any]]) -> dict[str, str]:
    """Solo preguntas y códigos conocidos (BR-028: nada de texto libre). Lanza ValueError si no."""
    clean: dict[str, str] = {}
    for qid, code in (answers or {}).items():
        q = QUESTIONS_BY_ID.get(qid)
        if q is None:
            raise ValueError(f"Pregunta desconocida: {qid}")
        if code not in {c for c, _ in q.options}:
            raise ValueError(f"Respuesta inválida para {qid}: {code}")
        clean[qid] = code
    return clean


def _in(values: Optional[list], value: Optional[str]) -> bool:
    return not values or value in values


def _matches(rule: Rule, pet: PetContext, *, service_code: Optional[str] = None,
             answers: Optional[dict[str, str]] = None) -> bool:
    c = rule.conditions
    if c.get("fallback"):
        return True
    # Edad mínima: sin fecha de nacimiento no descarta (casi siempre es un adulto). Edad máxima (cachorros):
    # sí exige conocer la edad.
    if c.get("min_age_months") is not None and pet.age_months is not None and pet.age_months < c["min_age_months"]:
        return False
    if c.get("max_age_months") is not None and (pet.age_months is None or pet.age_months > c["max_age_months"]):
        return False
    if c.get("min_weight_kg") is not None and (pet.weight_kg is None or pet.weight_kg < c["min_weight_kg"]):
        return False
    if c.get("max_weight_kg") is not None and (pet.weight_kg is None or pet.weight_kg > c["max_weight_kg"]):
        return False
    segments = c.get("segments")
    if segments and pet.segment not in segments:
        return False
    skin = c.get("skin_sensitive")  # True / False / None (cualquiera)
    if skin is not None and bool(pet.skin_sensitive) != skin:
        return False
    if not _in(c.get("services"), service_code):
        return False
    question = c.get("question")
    if question and (answers or {}).get(question) != c.get("answer"):
        return False
    return True


def recommend_service(rules: list[Rule], pet: PetContext, available_codes: set[str]) -> Optional[Rule]:
    """La regla de servicio activa de menor prioridad que aplica y cuyo servicio se puede comprar."""
    for rule in sorted((r for r in rules if r.kind == "service" and r.active), key=lambda r: (r.priority, r.id)):
        if rule.target_code in available_codes and _matches(rule, pet):
            return rule
    return None


def evaluate_addons(rules: list[Rule], pet: PetContext, *, service_code: Optional[str],
                    answers: dict[str, str], addon_codes: set[str]) -> AddonEvaluation:
    """Por adicional gana la regla de menor prioridad. REVISION_MANUAL no tiene adicional: marca la reserva."""
    out = AddonEvaluation(verdicts={code: AddonVerdict(code=code) for code in addon_codes})
    for rule in sorted((r for r in rules if r.kind == "addon" and r.active), key=lambda r: (r.priority, r.id)):
        if not _matches(rule, pet, service_code=service_code, answers=answers):
            continue
        if rule.action == REVIEW:
            out.review = out.review or rule
            continue
        if rule.action == HIDE_SERVICE_ADDONS:
            keep = set(rule.conditions.get("keep") or [])
            out.hide_except = keep if out.hide_except is None else out.hide_except & keep
            continue
        verdict = out.verdicts.get(rule.target_code or "")
        if verdict is None or verdict.action is not None:
            continue  # adicional no disponible para esta mascota, o ya lo decidió una regla de mayor prioridad
        verdict.action, verdict.rule_id, verdict.text = rule.action, rule.id, rule.text
        verdict.requires_photo = rule.requires_photo
    if out.hide_except is not None:
        for code, verdict in out.verdicts.items():
            if code not in out.hide_except and verdict.action is None:
                verdict.action = UNAVAILABLE
    return out
