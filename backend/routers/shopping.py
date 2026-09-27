"""Shopping-list routes: add a recipe's missing ingredients, tick them off, delete lists."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import ShoppingListItem
from pantry_store import format_quantity, normalize_ingredient_name, pantry_items_for
from recipe_store import get_recipe_or_404, recipe_ingredient_details
from recommender import ingredient_is_match
from schemas import ShoppingListRecipeRequest

router = APIRouter()


def serialize_shopping_item(item: ShoppingListItem) -> dict:
    return {
        "id": item.id,
        "user_id": item.user_id,
        "recipe_id": item.recipe_id,
        "ingredient": item.ingredient,
        "quantity": item.quantity,
        "checked": item.checked,
        "created_at": item.created_at,
    }


@router.get("/shopping-list/{user_id}")
def get_shopping_list(user_id: int, db: Session = Depends(get_db)):
    items = (
        db.query(ShoppingListItem)
        .filter(ShoppingListItem.user_id == user_id)
        .order_by(ShoppingListItem.checked.asc(), ShoppingListItem.id.desc())
        .all()
    )
    return [serialize_shopping_item(item) for item in items]


@router.post("/shopping-list/{user_id}/recipe/{recipe_id}")
def add_recipe_missing_to_shopping_list(
    user_id: int,
    recipe_id: int,
    request: ShoppingListRecipeRequest,
    db: Session = Depends(get_db),
):
    recipe = get_recipe_or_404(db, recipe_id)
    pantry_items = pantry_items_for(db, user_id)
    added = []
    for detail in recipe_ingredient_details(recipe, request.servings):
        if any(ingredient_is_match(detail["name"], item.ingredient) for item in pantry_items):
            continue
        existing = db.query(ShoppingListItem).filter(
            ShoppingListItem.user_id == user_id,
            ShoppingListItem.recipe_id == recipe_id,
            ShoppingListItem.ingredient == normalize_ingredient_name(detail["name"]),
            ShoppingListItem.checked.is_(False),
        ).first()
        if existing:
            continue
        item = ShoppingListItem(
            user_id=user_id,
            recipe_id=recipe_id,
            ingredient=normalize_ingredient_name(detail["name"]),
            quantity=format_quantity(float(detail["amount"]), detail["unit"]),
            checked=False,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        db.add(item)
        added.append(item)
    db.commit()
    for item in added:
        db.refresh(item)
    return {
        "message": f"Added {len(added)} missing ingredient{'s' if len(added) != 1 else ''} to your shopping list.",
        "added_items": [serialize_shopping_item(item) for item in added],
        "shopping_list": get_shopping_list(user_id, db),
    }


@router.delete("/shopping-list/{user_id}")
def clear_shopping_list(user_id: int, db: Session = Depends(get_db)):
    """Delete the whole shopping list when the user no longer wants it."""
    deleted = db.query(ShoppingListItem).filter(ShoppingListItem.user_id == user_id).delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted, "shopping_list": []}


@router.put("/shopping-list/item/{item_id}/toggle")
def toggle_shopping_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ShoppingListItem).filter(ShoppingListItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Shopping-list item not found.")
    item.checked = not item.checked
    db.flush()
    result = serialize_shopping_item(item)
    group = db.query(ShoppingListItem).filter(
        ShoppingListItem.user_id == item.user_id,
        ShoppingListItem.recipe_id == item.recipe_id,
    ).all()
    complete = bool(group) and all(entry.checked for entry in group)
    user_id = item.user_id
    deleted_ids = [entry.id for entry in group] if complete else []
    if complete:
        for entry in group:
            db.delete(entry)
    db.commit()
    return {**result, "group_completed": complete, "deleted_item_ids": deleted_ids,
            "shopping_list": get_shopping_list(user_id, db)}


@router.delete("/shopping-list/{user_id}/recipe/{recipe_id}")
def delete_recipe_shopping_list(user_id: int, recipe_id: int, db: Session = Depends(get_db)):
    """Delete exactly this user's selected meal list; 0 denotes unassigned groceries."""
    query = db.query(ShoppingListItem).filter(
        ShoppingListItem.user_id == user_id,
        ShoppingListItem.recipe_id == (None if recipe_id == 0 else recipe_id),
    )
    deleted = query.delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted, "shopping_list": get_shopping_list(user_id, db)}


@router.delete("/shopping-list/item/{item_id}")
def delete_shopping_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ShoppingListItem).filter(ShoppingListItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Shopping-list item not found.")
    db.delete(item)
    db.commit()
    return {"deleted": True, "item_id": item_id}
