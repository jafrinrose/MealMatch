"""Cooking routes: start a recipe, follow its steps, ask for help, and finish or cancel."""

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ai_services import cooking_assistant_question, general_cooking_assistant_question
from database import get_db
from impact import RESCUE_WINDOW_DAYS, cooking_impact
from models import CookingMessage, CookingSession, PantryItem, Recipe
from pantry_store import days_until, format_quantity, pantry_items_for, parse_pantry_quantity
from pantry_usage import amount_in_pantry_unit, display_unit, remaining_amount
from preference_store import get_preference_record, preference_lists
from recipe_store import get_recipe_or_404, recipe_ingredient_details, recipe_step_details, serialize_recipe
from recommender import ingredient_is_match
from schemas import CookRecipeRequest, CookingQuestionRequest, CookingStepRequest, GeneralAssistantRequest

router = APIRouter()


def get_active_cooking_session(db: Session, user_id: int) -> CookingSession | None:
    return (
        db.query(CookingSession)
        .filter(CookingSession.user_id == user_id, CookingSession.status == "active")
        .order_by(CookingSession.id.desc())
        .first()
    )


def active_session_or_404(db: Session, user_id: int, detail: str = "No active cooking session.") -> CookingSession:
    session = get_active_cooking_session(db, user_id)
    if not session:
        raise HTTPException(status_code=404, detail=detail)
    return session


def pantry_plan(session: CookingSession) -> list:
    """What the meal takes from the pantry, recorded when cooking started."""
    try:
        snapshot = json.loads(session.pantry_snapshot or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return snapshot if isinstance(snapshot, list) else []


def serialize_cooking_session(session: CookingSession, db: Session) -> dict:
    recipe = db.query(Recipe).filter(Recipe.id == session.recipe_id).first()
    messages = (
        db.query(CookingMessage)
        .filter(CookingMessage.session_id == session.id)
        .order_by(CookingMessage.id.asc())
        .all()
    )
    return {
        "id": session.id,
        "user_id": session.user_id,
        "recipe_id": session.recipe_id,
        "servings": session.servings,
        "started_at": session.started_at,
        "ready_at": session.ready_at,
        "status": session.status,
        "current_step": session.current_step,
        "recipe": serialize_recipe(recipe, db, session.user_id) if recipe else None,
        "messages": [
            {"id": message.id, "role": message.role, "text": message.content, "created_at": message.created_at}
            for message in messages
        ],
    }


@router.post("/recipes/{recipe_id}/cook/{user_id}")
def cook_recipe(
    recipe_id: int,
    user_id: int,
    request: CookRecipeRequest,
    db: Session = Depends(get_db),
):
    recipe = get_recipe_or_404(db, recipe_id)

    active_session = get_active_cooking_session(db, user_id)
    if active_session:
        raise HTTPException(
            status_code=409,
            detail="Finish or cancel your current cooking session before starting another recipe.",
        )

    pantry_items = pantry_items_for(db, user_id)
    # The pantry changes when the meal is ready (POST .../complete), not now: that
    # is when the food has been used, and "Changed my mind" then has nothing to undo.
    # The plan records which pantry item each ingredient will come from.
    pantry_snapshot = []
    for used in recipe_ingredient_details(recipe, request.servings):
        matches = [
            item for item in pantry_items
            if ingredient_is_match(used["name"], item.ingredient) and (days_until(item.expiry_date) or 0) >= 0
        ]
        if not matches:
            continue
        # With several matches ("avocado", "avocados"), use the one that expires first.
        pantry_item = min(matches, key=lambda item: (days_until(item.expiry_date) is None, days_until(item.expiry_date) or 0))
        pantry_snapshot.append({
            "pantry_item_id": pantry_item.id,
            "ingredient": pantry_item.ingredient,
            "recipe_ingredient": used["name"],
            "quantity": pantry_item.quantity,
            "expiry_date": pantry_item.expiry_date,
            "expiry_estimated": bool(pantry_item.expiry_estimated),
            "category": pantry_item.category,
            "recipe_amount": float(used["amount"]),
            "recipe_unit": used["unit"],
            "quantity_used": format_quantity(float(used["amount"]), used["unit"]),
            "deduct_on_complete": True,
            "deducted": False,
            "amount_used": None,
        })

    started_at = datetime.now(timezone.utc)
    total_minutes = (recipe.prep_time if recipe.prep_time is not None else 10) + (recipe.cooking_time or 0)
    session = CookingSession(
        user_id=user_id,
        recipe_id=recipe_id,
        servings=request.servings,
        started_at=started_at.isoformat(),
        ready_at=(started_at + timedelta(minutes=total_minutes)).isoformat(),
        status="active",
        current_step=0,
        pantry_snapshot=json.dumps(pantry_snapshot),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "message": f"Cooking {recipe.title}. Your pantry updates when the meal is ready.",
        "planned_items": [entry["ingredient"] for entry in pantry_snapshot],
        "cooking_session": serialize_cooking_session(session, db),
    }


@router.get("/cooking-session/{user_id}")
def get_cooking_session(user_id: int, db: Session = Depends(get_db)):
    session = get_active_cooking_session(db, user_id)
    return serialize_cooking_session(session, db) if session else None


@router.get("/home-insights/{user_id}")
def get_home_insights(user_id: int, db: Session = Depends(get_db)):
    sessions = db.query(CookingSession).filter(CookingSession.user_id == user_id, CookingSession.status == "completed").all()
    titles = dict(db.query(Recipe.id, Recipe.title).all())
    pantry = pantry_items_for(db, user_id)
    return cooking_impact(sessions, titles, pantry_items=pantry)


@router.put("/cooking-session/{user_id}/step")
def update_cooking_step(
    user_id: int,
    request: CookingStepRequest,
    db: Session = Depends(get_db),
):
    session = active_session_or_404(db, user_id)
    session.current_step = request.current_step
    db.commit()
    db.refresh(session)
    return serialize_cooking_session(session, db)


@router.post("/cooking-session/{user_id}/complete")
def complete_cooking_session(user_id: int, db: Session = Depends(get_db)):
    session = active_session_or_404(db, user_id)
    snapshot = pantry_plan(session)
    started_at = datetime.fromisoformat(session.started_at.replace("Z", "+00:00"))
    rescued = []
    for item in snapshot:
        try:
            # Local date, like the "Use soon" panel: in UTC+8 the UTC date is a day behind until 8 am.
            days_remaining = (datetime.fromisoformat(str(item.get("expiry_date", ""))).date() - started_at.astimezone().date()).days
        except ValueError:
            continue
        if 0 <= days_remaining <= RESCUE_WINDOW_DAYS:
            rescued.append(str(item.get("ingredient", "ingredient")))
    updated_items, removed_items, unchanged_items = apply_pantry_usage(db, user_id, snapshot)
    session.pantry_snapshot = json.dumps(snapshot)
    session.status = "completed"
    db.commit()
    changed = len(updated_items) + len(removed_items)
    message = f"Meal ready. {changed} pantry item{'s' if changed != 1 else ''} updated." if changed else "Meal ready. Enjoy!"
    if rescued:
        message += f" Kitchen win: {len(rescued)} ingredient{'s' if len(rescued) != 1 else ''} used before expiry."
    return {
        "message": message,
        "status": "completed",
        "rescued_items": rescued,
        "updated_items": updated_items,
        "removed_items": removed_items,
        "unchanged_items": unchanged_items,
    }


def apply_pantry_usage(db: Session, user_id: int, snapshot: list) -> tuple[list[dict], list[str], list[str]]:
    """Take what the meal used out of the pantry, converting units where needed.

    Entries deducted when cooking started (sessions from before this change) are
    skipped. Each entry records what was taken, for the waste-impact record.
    """
    items = {item.id: item for item in pantry_items_for(db, user_id)}
    removed_ids: set[int] = set()
    updated: dict[int, dict] = {}
    removed: list[str] = []
    unchanged: list[str] = []
    for entry in snapshot:
        if not isinstance(entry, dict) or not entry.get("deduct_on_complete") or entry.get("deducted"):
            continue
        item = items.get(entry.get("pantry_item_id")) or next(
            (candidate for candidate in items.values() if candidate.ingredient == entry.get("ingredient")), None,
        )
        if item is None or item.id in removed_ids:
            continue
        have, unit = parse_pantry_quantity(item.quantity)
        if have is None:
            # "carton" with no number is one carton.
            have, unit = 1.0, (item.quantity or "").strip()
        used = amount_in_pantry_unit(
            str(entry.get("recipe_ingredient") or item.ingredient), float(entry.get("recipe_amount") or 1),
            str(entry.get("recipe_unit") or ""), unit,
        )
        if used is None or have <= 0:
            unchanged.append(item.ingredient)
            continue
        left = remaining_amount(have, used, unit)
        entry.update({
            "deducted": True,
            "amount_used": round(min(have, used), 3),
            "pantry_quantity_used": format_quantity(round(min(have, used), 2), unit),
        })
        if left <= 0:
            db.delete(item)
            removed_ids.add(item.id)
            updated.pop(item.id, None)
            removed.append(item.ingredient)
        else:
            item.quantity = format_quantity(left, display_unit(left, unit))
            updated[item.id] = {"ingredient": item.ingredient, "quantity": item.quantity}
    return list(updated.values()), removed, unchanged


@router.post("/cooking-session/{user_id}/cancel")
def cancel_cooking_session(user_id: int, db: Session = Depends(get_db)):
    session = active_session_or_404(db, user_id)
    snapshot = pantry_plan(session)

    # Only sessions started before the pantry moved to "meal is ready" changed it at
    # the start; for every newer session there is nothing to restore.
    restored = [entry for entry in snapshot if isinstance(entry, dict) and entry.get("deducted") and not entry.get("deduct_on_complete")]
    for original in restored:
        pantry_item = (
            db.query(PantryItem)
            .filter(
                PantryItem.user_id == user_id,
                PantryItem.ingredient == original["ingredient"],
            )
            .first()
        )
        if pantry_item:
            pantry_item.quantity = original.get("quantity", "")
            pantry_item.expiry_date = original.get("expiry_date", "")
            pantry_item.expiry_estimated = bool(original.get("expiry_estimated", False))
            pantry_item.category = original.get("category", "other")
        else:
            db.add(PantryItem(
                user_id=user_id,
                ingredient=original["ingredient"],
                quantity=original.get("quantity", ""),
                expiry_date=original.get("expiry_date", ""),
                expiry_estimated=bool(original.get("expiry_estimated", False)),
                category=original.get("category", "other"),
            ))

    session.status = "cancelled"
    db.commit()
    return {
        "message": "Cooking cancelled and pantry quantities restored." if restored else "Cooking cancelled. Your pantry is unchanged.",
        "status": "cancelled",
        "restored_items": len(restored),
    }


@router.post("/cooking-session/{user_id}/ask")
def ask_during_cooking(
    user_id: int,
    request: CookingQuestionRequest,
    db: Session = Depends(get_db),
):
    session = active_session_or_404(db, user_id, "Start a recipe before using cooking mode chat.")
    recipe = get_recipe_or_404(db, session.recipe_id)

    now = datetime.now(timezone.utc).isoformat()
    user_message = CookingMessage(
        session_id=session.id,
        role="user",
        content=request.question.strip(),
        created_at=now,
    )
    db.add(user_message)
    steps = recipe_step_details(recipe)
    current_step = min(max(session.current_step or 0, 0), max(len(steps) - 1, 0))
    answer = cooking_assistant_question(
        recipe=recipe,
        question=request.question.strip(),
        current_step=current_step,
        step_details=steps,
    )
    db.add(CookingMessage(
        session_id=session.id,
        role="assistant",
        content=answer,
        created_at=datetime.now(timezone.utc).isoformat(),
    ))
    db.commit()
    db.refresh(session)
    return serialize_cooking_session(session, db)


@router.post("/assistant/{user_id}")
def general_assistant(
    user_id: int,
    request: GeneralAssistantRequest,
    db: Session = Depends(get_db),
):
    pantry_items = pantry_items_for(db, user_id)
    saved = preference_lists(get_preference_record(db, user_id))
    answer = general_cooking_assistant_question(
        pantry_ingredients=[item.ingredient for item in pantry_items],
        dietary_restrictions=saved["dietary_restrictions"],
        allergies=saved["allergies"],
        question=request.question.strip(),
    )
    return {"answer": answer, "context": "pantry", "active_recipe": None}
