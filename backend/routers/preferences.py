"""Preference routes: the diets, allergies and cuisines a cook has saved."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import UserPreference
from preference_store import LIST_FIELDS, get_preference_record, list_to_storage, preference_lists
from schemas import UserPreferenceRequest

router = APIRouter()


@router.get("/preferences/{user_id}")
def get_user_preferences(
    user_id: int,
    db: Session = Depends(get_db),
):
    preferences = get_preference_record(db, user_id)

    return {
        "user_id": user_id,
        **preference_lists(preferences),
        "max_cooking_time": preferences.max_cooking_time if preferences else None,
        "skill_level": preferences.skill_level if preferences else "beginner",
        "onboarding_complete": preferences.onboarding_complete if preferences else False,
    }


@router.put("/preferences/{user_id}")
def save_user_preferences(
    user_id: int,
    request: UserPreferenceRequest,
    db: Session = Depends(get_db),
):
    preferences = get_preference_record(db, user_id)

    if not preferences:
        preferences = UserPreference(
            user_id=user_id,
        )

        db.add(preferences)

    for field in LIST_FIELDS:
        setattr(preferences, field, list_to_storage(getattr(request, field)))

    preferences.max_cooking_time = request.max_cooking_time
    preferences.skill_level = request.skill_level
    preferences.onboarding_complete = request.onboarding_complete

    db.commit()
    db.refresh(preferences)

    return {
        "message": "Preferences saved.",
        "user_id": user_id,
    }
