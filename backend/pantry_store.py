"""Pantry records: ingredient names, food groups, estimated expiry dates and amounts."""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import PantryItem


def normalize_ingredient_name(ingredient: str) -> str:
    return ingredient.strip().lower()


def normalize_ingredient_list(ingredients: list[str]) -> list[str]:
    cleaned = []
    seen = set()

    for ingredient in ingredients:
        normalized = normalize_ingredient_name(ingredient)

        if normalized and normalized not in seen:
            cleaned.append(normalized)
            seen.add(normalized)

    return cleaned


PANTRY_CATEGORY_KEYWORDS = {
    "fruit": {"apple", "banana", "berries", "berry", "cherry", "grape", "kiwi", "lemon", "lime", "mango", "melon", "orange", "peach", "pear", "pineapple", "plum", "strawberry"},
    "vegetables": {"asparagus", "avocado", "broccoli", "cabbage", "carrot", "celery", "corn", "courgette", "cucumber", "eggplant", "garlic", "herb", "kale", "lettuce", "mushroom", "onion", "pea", "pepper", "potato", "spinach", "tomato", "vegetable", "zucchini"},
    "eggs": {"egg", "eggs"},
    "dairy": {"brie", "butter", "cheddar", "cheese", "cream", "feta", "milk", "mozzarella", "parmesan", "yogurt", "yoghurt"},
    "meat": {"bacon", "beef", "chicken", "ham", "lamb", "meat", "mince", "pork", "sausage", "steak", "turkey"},
    "seafood": {"anchovy", "crab", "fish", "lobster", "prawn", "salmon", "sardine", "seafood", "shrimp", "tuna"},
    "grains": {"barley", "cereal", "couscous", "flour", "granola", "grain", "noodle", "oat", "pasta", "quinoa", "rice"},
    "bakery": {"bagel", "bread", "bun", "cake", "croissant", "muffin", "pastry", "pita", "tortilla", "wrap"},
    "condiments": {"dressing", "jam", "ketchup", "mayonnaise", "mustard", "nutella", "pesto", "relish", "salsa", "sauce", "spread", "vinegar"},
    "snacks": {"biscuit", "candy", "chip", "chocolate", "cookie", "cracker", "crisp", "popcorn", "pretzel", "snack", "sweet"},
    "beverages": {"coffee", "cola", "drink", "juice", "lemonade", "smoothie", "soda", "tea", "water"},
    "frozen": {"frozen"},
    "pantry": {"bean", "broth", "canned", "chickpea", "honey", "lentil", "nut", "oil", "salt", "seed", "spice", "stock", "sugar", "tin", "yeast"},
}


def classify_pantry_category(ingredient: str) -> str:
    normalized = normalize_ingredient_name(ingredient)
    if "ice cream" in normalized:
        return "frozen"
    if "peanut butter" in normalized or "nut butter" in normalized:
        return "condiments"
    words = set(re.findall(r"[a-z]+", normalized))
    words.update(word[:-1] for word in tuple(words) if word.endswith("s") and len(word) > 3)

    # Product-form words are more specific than their flavour or ingredient.
    # For example, strawberry jam is a condiment and potato chips are snacks.
    for category in ("frozen", "condiments", "snacks", "beverages"):
        if words.intersection(PANTRY_CATEGORY_KEYWORDS[category]):
            return category

    for category, keywords in PANTRY_CATEGORY_KEYWORDS.items():
        if words.intersection(keywords):
            return category

    return "other"


# Conservative refrigerated-storage defaults derived from the USDA FoodKeeper
# categories. These are freshness estimates, not food-safety guarantees.
SHELF_LIFE_DAYS = {
    "fruit": 7,
    "vegetables": 7,
    "dairy": 7,
    "meat": 2,
    "seafood": 2,
    "eggs": 21,
    "grains": 120,
    "bakery": 5,
    "pantry": 180,
    "condiments": 60,
    "snacks": 60,
    "beverages": 10,
    "frozen": 90,
    "other": 7,
}


def estimated_expiry_date(ingredient: str, category: str = "other") -> str:
    resolved_category = category if category in SHELF_LIFE_DAYS else classify_pantry_category(ingredient)
    normalized = normalize_ingredient_name(ingredient)
    days = SHELF_LIFE_DAYS.get(resolved_category, 7)
    if any(word in normalized for word in ("spinach", "lettuce", "herb", "berries", "strawberry")):
        days = 4
    elif any(word in normalized for word in ("avocado", "banana", "mushroom")):
        days = 5
    elif any(word in normalized for word in ("hard cheese", "parmesan", "cheddar")):
        days = 21
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def pantry_items_for(db: Session, user_id: int) -> list[PantryItem]:
    return db.query(PantryItem).filter(PantryItem.user_id == user_id).all()


def save_or_update_pantry_item(
    db: Session,
    user_id: int,
    ingredient: str,
    quantity: str = "",
    expiry_date: str = "",
    category: str = "other",
):
    cleaned_ingredient = normalize_ingredient_name(ingredient)
    requested_category = category.strip().lower()
    resolved_category = (
        requested_category
        if requested_category in PANTRY_CATEGORY_KEYWORDS and requested_category != "other"
        else classify_pantry_category(cleaned_ingredient)
    )
    entered_expiry = expiry_date.strip()
    resolved_expiry = entered_expiry or estimated_expiry_date(cleaned_ingredient, resolved_category)

    if not cleaned_ingredient:
        return None

    existing_item = (
        db.query(PantryItem)
        .filter(
            PantryItem.user_id == user_id,
            PantryItem.ingredient == cleaned_ingredient,
        )
        .first()
    )

    if existing_item:
        existing_item.quantity = quantity.strip() or existing_item.quantity
        if entered_expiry:
            existing_item.expiry_date = entered_expiry
            existing_item.expiry_estimated = False
        elif not existing_item.expiry_date:
            existing_item.expiry_date = resolved_expiry
            existing_item.expiry_estimated = True
        existing_item.category = resolved_category
        db.commit()
        db.refresh(existing_item)
        return existing_item

    item = PantryItem(
        user_id=user_id,
        ingredient=cleaned_ingredient,
        quantity=quantity.strip(),
        expiry_date=resolved_expiry,
        expiry_estimated=not bool(entered_expiry),
        category=resolved_category,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


def parse_pantry_quantity(quantity: str) -> tuple[float | None, str]:
    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(.*)$", quantity or "")

    if not match:
        return None, ""

    return float(match.group(1)), match.group(2).strip()


def days_until(expiry_date: str | None) -> int | None:
    try:
        return (datetime.fromisoformat(str(expiry_date)).date() - datetime.now().date()).days
    except (TypeError, ValueError):
        return None


def format_quantity(amount: float, unit: str) -> str:
    display_amount = str(int(amount)) if amount.is_integer() else f"{amount:.2f}".rstrip("0").rstrip(".")
    return f"{display_amount} {unit}".strip()
