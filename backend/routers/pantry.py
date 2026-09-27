"""Pantry routes: list, add, edit and remove ingredients."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import PantryItem
from pantry_store import (
    PANTRY_CATEGORY_KEYWORDS,
    classify_pantry_category,
    estimated_expiry_date,
    normalize_ingredient_name,
    pantry_items_for,
    save_or_update_pantry_item,
)
from schemas import PantryItemUpdateRequest

router = APIRouter()


@router.get("/pantry/{user_id}")
def get_pantry(user_id: int, db: Session = Depends(get_db)):
    items = pantry_items_for(db, user_id)
    changed = False
    for item in items:
        inferred = classify_pantry_category(item.ingredient)
        if (not item.category or item.category in {"other", "produce", "protein"}) and inferred != "other":
            item.category = inferred
            changed = True
        if not item.expiry_date:
            item.expiry_date = estimated_expiry_date(item.ingredient, inferred)
            item.expiry_estimated = True
            changed = True
    if changed:
        db.commit()
        for item in items:
            db.refresh(item)
    return items


@router.post("/pantry/{user_id}")
def add_pantry_item(
    user_id: int,
    ingredient: str,
    quantity: str = "",
    expiry_date: str = "",
    category: str = "other",
    db: Session = Depends(get_db),
):
    item = save_or_update_pantry_item(
        db=db,
        user_id=user_id,
        ingredient=ingredient,
        quantity=quantity,
        expiry_date=expiry_date,
        category=category,
    )

    if item is None:
        raise HTTPException(status_code=400, detail="Ingredient cannot be empty.")

    return {
        "message": "Ingredient saved successfully.",
        "item": item,
    }


@router.put("/pantry/item/{item_id}")
def update_pantry_item(
    item_id: int,
    request: PantryItemUpdateRequest,
    db: Session = Depends(get_db),
):
    item = db.query(PantryItem).filter(PantryItem.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Pantry item not found.")

    cleaned_ingredient = normalize_ingredient_name(request.ingredient)

    if not cleaned_ingredient:
        raise HTTPException(status_code=400, detail="Ingredient cannot be empty.")

    duplicate = (
        db.query(PantryItem)
        .filter(
            PantryItem.user_id == item.user_id,
            PantryItem.ingredient == cleaned_ingredient,
            PantryItem.id != item_id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(status_code=409, detail="That ingredient is already in your pantry.")

    item.ingredient = cleaned_ingredient
    item.quantity = request.quantity.strip()
    requested_category = request.category.strip().lower()
    item.category = requested_category if requested_category in PANTRY_CATEGORY_KEYWORDS else classify_pantry_category(cleaned_ingredient)
    entered_expiry = request.expiry_date.strip()
    item.expiry_date = entered_expiry or estimated_expiry_date(cleaned_ingredient, item.category)
    item.expiry_estimated = not bool(entered_expiry)
    db.commit()
    db.refresh(item)

    return {"message": "Pantry item updated.", "item": item}


@router.delete("/pantry/item/{item_id}")
def delete_pantry_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(PantryItem).filter(PantryItem.id == item_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Pantry item not found.")

    db.delete(item)
    db.commit()

    return {"deleted": True}
