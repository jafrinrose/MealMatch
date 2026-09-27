"""Saved cooking preferences: diets, allergies, disliked foods and cuisines."""

from sqlalchemy.orm import Session

from models import UserPreference
from pantry_store import normalize_ingredient_list

# Each is stored as one comma-separated text column.
LIST_FIELDS = ("dietary_restrictions", "allergies", "disliked_ingredients", "preferred_cuisines")


def list_to_storage(items: list[str]) -> str:
    return ",".join(normalize_ingredient_list(items))


def storage_to_list(value: str | None) -> list[str]:
    if not value:
        return []

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def get_preference_record(db: Session, user_id: int) -> UserPreference | None:
    return (
        db.query(UserPreference)
        .filter(UserPreference.user_id == user_id)
        .first()
    )


def preference_lists(preferences: UserPreference | None) -> dict[str, list[str]]:
    """Every saved list by field name; all empty when the cook has saved no preferences."""
    return {field: storage_to_list(getattr(preferences, field)) if preferences else [] for field in LIST_FIELDS}
