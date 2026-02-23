from uuid import UUID

from app.modules.commerce.domain import addons_rules


def test_addon_ids_are_stable():
    assert addons_rules.ADDON_CEPILLADO_ID == UUID("66666666-6666-6666-6666-666666666666")
    assert addons_rules.ADDON_DESLANADO_ID == UUID("77777777-7777-7777-7777-777777777777")
    assert addons_rules.ADDON_DESMOTADO_ID == UUID("88888888-8888-8888-8888-888888888888")


def test_deslanado_required_contains_expected_breeds():
    assert "husky" in addons_rules.DESLANADO_REQUIRED_BREEDS
    assert "golden_retriever" in addons_rules.DESLANADO_REQUIRED_BREEDS


def test_deslanado_applicable_is_union_of_required_and_optional():
    applicable = addons_rules.deslanado_applicable_breeds()
    assert addons_rules.DESLANADO_REQUIRED_BREEDS.issubset(applicable)
    assert addons_rules.DESLANADO_OPTIONAL_BREEDS.issubset(applicable)


def test_desmotado_applicable_is_union_of_risk_sets():
    applicable = addons_rules.desmotado_applicable_breeds()
    assert addons_rules.DESMOTADO_HIGH_RISK_BREEDS.issubset(applicable)
    assert addons_rules.DESMOTADO_MEDIUM_RISK_BREEDS.issubset(applicable)
