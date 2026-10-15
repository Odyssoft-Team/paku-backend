"""Feature 0006 — el admin asigna el pelaje de cada raza; mestizos por pelaje; variantes de pelo."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.modules.catalog.app.use_cases import _breed_fields
from app.modules.catalog.domain.breeds_data import BREEDS_CATALOG
from app.modules.pets.domain.weight_policy import weight_editable_from
from app.modules.store.domain.pricing import FALLBACK_CATEGORY, category_for_coat

DOGS = {b["id"]: b for g in BREEDS_CATALOG if g["species"] == "dog" for b in g["breeds"]}


def test_category_for_coat():
    assert category_for_coat("double_long") == "double_long"
    assert category_for_coat(None) == FALLBACK_CATEGORY
    assert category_for_coat("otros") == FALLBACK_CATEGORY


def test_breed_fields_derive_group_and_validate():
    assert _breed_fields({"coat_type": "curly_no_undercoat"}) == {
        "coat_type": "curly_no_undercoat", "coat_group": "single"}
    assert _breed_fields({"coat_type": "double_short"})["coat_group"] == "double"
    # Quitar el pelaje: se cobra como mestizo
    assert _breed_fields({"coat_type": None}) == {"coat_type": None, "coat_group": None}
    assert _breed_fields({"photo_url": "  ", "description": " Pelo corto "}) == {
        "photo_url": None, "description": "Pelo corto"}
    with pytest.raises(HTTPException) as exc:
        _breed_fields({"coat_type": "official"})
    assert exc.value.status_code == 422 and exc.value.detail["code"] == "COAT_TYPE_INVALID"


def test_six_mixed_breeds_one_per_coat():
    mixed = [b for b in DOGS.values() if b.get("is_mixed")]
    assert sorted(b["coat_type"] for b in mixed) == sorted([
        "simple_short", "simple_medium_long", "curly_no_undercoat",
        "double_short", "double_long", "mixed_curly_undercoat",
    ])
    assert all(b.get("description") for b in mixed)
    assert DOGS["dog_mixed"].get("is_active") is False


@pytest.mark.parametrize(
    "short, long_, short_coat, long_coat",
    [
        ("dachshund", "dachshund_largo", "simple_short", "simple_medium_long"),
        ("chihuahua", "chihuahua_largo", "simple_short", "simple_medium_long"),
        ("pastor_aleman", "pastor_aleman_largo", "double_short", "double_long"),
        ("chow_chow", "chow_chow_largo", "double_short", "double_long"),
        ("cocker_spaniel", "cocker_spaniel_largo", "simple_medium_long", "double_long"),
    ],
)
def test_coat_variants(short, long_, short_coat, long_coat):
    assert DOGS[short]["coat_type"] == short_coat
    assert DOGS[long_]["coat_type"] == long_coat


def test_weight_editable_from():
    now = datetime(2026, 10, 14, tzinfo=timezone.utc)
    assert weight_editable_from(None, now) is None                       # nunca cambió: puede
    assert weight_editable_from(now - timedelta(days=31), now) is None   # pasaron 30 días
    assert weight_editable_from(now - timedelta(days=10), now) == now + timedelta(days=20)


def test_breed_photo_must_be_uploaded_or_url():
    assert _breed_fields({"photo_url": "catalog/0b6e/photo_1.webp"})["photo_url"] == "catalog/0b6e/photo_1.webp"
    assert _breed_fields({"photo_url": "https://cdn.paku.pe/m1.jpg"})["photo_url"].startswith("https://")
    with pytest.raises(HTTPException) as exc:
        _breed_fields({"photo_url": "pets/123/profile.jpg"})
    assert exc.value.detail["code"] == "PHOTO_URL_INVALID"


def test_catalog_media_prefix():
    from uuid import uuid4
    from app.media.gcs import build_object_name
    from app.media.schemas import MediaEntityType
    name = build_object_name(MediaEntityType.catalog, uuid4(), "image/jpeg")
    assert name.startswith("catalog/") and "/photo_" in name
