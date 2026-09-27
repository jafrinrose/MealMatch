"""Recipe records: ingredients, steps and timings, diet and allergy checks, and AI recipes."""

import json
import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ingredient_matching import analyse, singular
from models import Recipe, SavedRecipe, UserPreference
from pantry_store import normalize_ingredient_name
from preference_store import storage_to_list
from recipe_relevance import savoury_ingredients_for_dessert
from recommender import allergy_conflicts, dietary_conflict_reason


INGREDIENT_AMOUNTS = {
    "chicken": (180, "g"),
    "chicken thigh": (2, "pieces"),
    "rice": (1, "cup"),
    "spinach": (2, "cups"),
    "soy sauce": (1, "tbsp"),
    "garlic": (2, "cloves"),
    "pasta": (180, "g"),
    "tomato": (2, "pieces"),
    "cheese": (0.5, "cup"),
    "olive oil": (1, "tbsp"),
    "egg": (2, "pieces"),
    "carrot": (1, "piece"),
    "peas": (0.5, "cup"),
    "onion": (1, "piece"),
    "butter": (1, "tbsp"),
    "yogurt": (1, "cup"),
    "berries": (1, "cup"),
    "granola": (0.5, "cup"),
    "honey": (1, "tbsp"),
    "oats": (0.5, "cup"),
    "milk": (1, "cup"),
    "banana": (1, "piece"),
}


def recipe_ingredient_details(recipe: Recipe, servings: int = 1) -> list[dict]:
    if recipe.ingredient_details:
        try:
            stored_details = json.loads(recipe.ingredient_details)
            if isinstance(stored_details, list) and stored_details:
                return [
                    {
                        **item,
                        "amount": float(item.get("amount", 1)) * servings,
                    }
                    for item in stored_details
                    if item.get("name")
                ]
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    details = []

    for raw_name in recipe.ingredients.split(","):
        name = normalize_ingredient_name(raw_name)
        amount, unit = INGREDIENT_AMOUNTS.get(name, (1, "portion"))
        scaled_amount = amount * servings

        details.append({
            "name": name,
            "amount": scaled_amount,
            "unit": unit,
        })

    return details


def recipe_instruction_steps(recipe: Recipe) -> list[str]:
    blocks = [
        re.sub(r"^\s*step\s*\d+\s*", "", block, flags=re.IGNORECASE).strip()
        for block in re.split(r"(?:\r?\n){2,}", recipe.instructions.strip())
    ]
    blocks = [block for block in blocks if block]
    if len(blocks) > 1:
        return blocks

    steps = [
        re.sub(r"^\s*step\s*\d+\s*", "", step, flags=re.IGNORECASE).strip()
        for step in re.split(r"(?:\r?\n)+|(?<=[.!?])\s+", recipe.instructions.strip())
        if re.sub(r"^\s*step\s*\d+\s*", "", step, flags=re.IGNORECASE).strip()
    ]
    return steps


def recipe_step_details(recipe: Recipe) -> list[dict]:
    """Return realistic per-step durations, preserving model-provided timing when available."""
    if recipe.step_details:
        try:
            stored = json.loads(recipe.step_details)
            if isinstance(stored, list) and stored:
                cleaned = [
                    {
                        "instruction": str(item.get("instruction", "")).strip(),
                        "minutes": max(1, int(item.get("minutes", 1))),
                    }
                    for item in stored
                    if isinstance(item, dict) and str(item.get("instruction", "")).strip()
                ]
                if cleaned:
                    return cleaned
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    steps = recipe_instruction_steps(recipe)
    if not steps:
        return []

    total_minutes = max(len(steps), (recipe.prep_time or 10) + (recipe.cooking_time or 0))
    explicit: list[int | None] = []
    weights = []
    for step in steps:
        match = re.search(r"(\d+)\s*(?:[-–]\s*(\d+)\s*)?(?:minutes?|mins?)\b", step, re.IGNORECASE)
        if match:
            start = int(match.group(1))
            end = int(match.group(2) or start)
            explicit.append(max(1, round((start + end) / 2)))
        else:
            explicit.append(None)

        lowered = step.lower()
        if re.search(r"bake|roast|simmer|braise|boil|cook until|fry", lowered):
            weights.append(2.4)
        elif re.search(r"chop|slice|dice|peel|prepare|marinate", lowered):
            weights.append(1.2)
        elif re.search(r"serve|garnish|plate|enjoy", lowered):
            weights.append(0.35)
        else:
            weights.append(0.8)

    available = max(len([value for value in explicit if value is None]), total_minutes - sum(value or 0 for value in explicit))
    flexible_weight = sum(weight for weight, value in zip(weights, explicit) if value is None) or 1
    durations = [
        value if value is not None else max(1, round(available * weight / flexible_weight))
        for value, weight in zip(explicit, weights)
    ]
    return [
        {"instruction": instruction, "minutes": duration}
        for instruction, duration in zip(steps, durations)
    ]


def recipe_is_safe_for_preferences(recipe: Recipe, preferences: UserPreference | None) -> bool:
    return recipe_is_allergy_safe(recipe, preferences) and not recipe_diet_conflicts(recipe, preferences)


def recipe_is_allergy_safe(recipe: Recipe, preferences: UserPreference | None) -> bool:
    """Allergies are never relaxed: a conflicting recipe is not shown anywhere."""
    if not preferences:
        return True
    ingredients = [item["name"] for item in recipe_ingredient_details(recipe)]
    return not allergy_conflicts(ingredients, storage_to_list(preferences.allergies))


def recipe_diet_conflicts(recipe: Recipe, preferences: UserPreference | None) -> list[dict]:
    """Saved diets this recipe breaks, with the ingredients responsible."""
    if not preferences or not storage_to_list(preferences.dietary_restrictions):
        return []
    ingredients = [item["name"] for item in recipe_ingredient_details(recipe)]
    return dietary_conflict_reason(ingredients, storage_to_list(preferences.dietary_restrictions))


def get_recipe_or_404(db: Session, recipe_id: int) -> Recipe:
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found.")
    return recipe


def serialize_recipe(recipe: Recipe, db: Session | None = None, user_id: int | None = None) -> dict:
    saved = False
    if db is not None and user_id is not None:
        saved = db.query(SavedRecipe).filter(
            SavedRecipe.user_id == user_id,
            SavedRecipe.recipe_id == recipe.id,
        ).first() is not None

    return {
        "id": recipe.id,
        "title": recipe.title,
        "ingredients": recipe.ingredients,
        "ingredient_details": recipe_ingredient_details(recipe),
        "instructions": recipe.instructions,
        "instruction_steps": recipe_instruction_steps(recipe),
        "step_details": recipe_step_details(recipe),
        "cooking_time": recipe.cooking_time,
        "prep_time": recipe.prep_time if recipe.prep_time is not None else 10,
        "total_time": (recipe.prep_time if recipe.prep_time is not None else 10) + (recipe.cooking_time or 0),
        "difficulty": recipe.difficulty,
        "cuisine": recipe.cuisine,
        "calories": recipe.calories,
        "servings": recipe.servings or 2,
        # AI recipes have no photo: the client shows the emojis of their main foods.
        "image_url": "" if recipe.source == "MealMatch AI" else (recipe.image_url or ""),
        "source": recipe.source or "MealMatch",
        "source_id": recipe.source_id or "",
        "saved": saved,
    }


def clean_model_text(value: str) -> str:
    """Repair common mis-encoded characters in model output ("Â°C" -> "°C")."""
    return (str(value).replace("Â°", "°").replace("Â", "").replace("â€™", "’").replace("â€“", "–").replace("â€”", "—")).strip()


def recipe_from_generated_payload(generated: dict) -> Recipe | None:
    """Convert validated LLM JSON into an unsaved Recipe record."""
    ingredient_details = []
    for item in generated.get("ingredients", []):
        if not isinstance(item, dict) or not item.get("name"):
            continue
        try:
            amount = float(item.get("amount", 1))
        except (TypeError, ValueError):
            amount = 1
        ingredient_details.append({
            "name": normalize_ingredient_name(str(item["name"])),
            "amount": max(amount, 0.01),
            "unit": str(item.get("unit", "portion")).strip() or "portion",
        })

    step_details = []
    for step in generated.get("steps", []):
        if isinstance(step, dict):
            instruction = clean_model_text(step.get("instruction", ""))
            try:
                minutes = max(1, int(step.get("minutes", 1)))
            except (TypeError, ValueError):
                minutes = 1
        else:
            instruction = clean_model_text(step)
            minutes = 1
        if instruction:
            step_details.append({"instruction": instruction, "minutes": minutes})

    if not ingredient_details or len(step_details) < 2:
        return None

    def positive_integer(field: str, fallback: int) -> int:
        try:
            return max(1, int(generated.get(field, fallback)))
        except (TypeError, ValueError):
            return fallback

    try:
        calories = max(0, int(generated.get("calories", 0)))
    except (TypeError, ValueError):
        calories = 0

    title = clean_model_text(generated.get("title", "Pantry recipe")) or "Pantry recipe"
    return Recipe(
        title=title,
        ingredients=",".join(item["name"] for item in ingredient_details),
        ingredient_details=json.dumps(ingredient_details),
        instructions="\n".join(step["instruction"] for step in step_details),
        step_details=json.dumps(step_details),
        prep_time=positive_integer("prep_time", 10),
        cooking_time=positive_integer("cooking_time", 20),
        servings=positive_integer("servings", 2),
        difficulty=str(generated.get("difficulty", "Beginner")),
        cuisine=str(generated.get("cuisine", "Fusion")),
        calories=calories,
        source="MealMatch AI",
        source_id="",
        image_url="",
    )


TITLE_FILLER = {"recipe", "the", "a", "an", "with", "and", "homemade", "style"}


def recipe_title_key(title: str) -> tuple[str, ...]:
    """Words that identify a dish name, so "Classic Brownies" and "classic brownie" are the same."""
    return tuple(sorted({singular(word) for word in re.findall(r"[a-z]+", title.lower())} - TITLE_FILLER))


def ingredient_similarity(first: list[str], second: list[str]) -> float:
    heads = lambda names: {analyse(name).head for name in names} - {""}
    a, b = heads(first), heads(second)
    return len(a & b) / len(a | b) if a | b else 0.0


def same_dish(recipe: Recipe, other: Recipe, threshold: float = 0.75) -> bool:
    """A repeat of another AI recipe: the same name, or nearly the same ingredients."""
    names = lambda item: [part for part in (item.ingredients or "").split(",") if part.strip()]
    return (
        recipe_title_key(recipe.title) == recipe_title_key(other.title)
        or ingredient_similarity(names(recipe), names(other)) >= threshold
    )


def browsable_recipes(db: Session) -> list[Recipe]:
    """Recipes with a photo plus every AI recipe, each once.

    AI recipes were added after the photo recipes without checking, so an AI
    recipe that had been given a photo was listed twice and showed as two cards
    (user testing, round 2).
    """
    all_recipes = [recipe for recipe in db.query(Recipe).all() if ai_recipe_is_coherent(recipe)]
    if not any(recipe.image_url for recipe in all_recipes):
        return all_recipes
    return [recipe for recipe in all_recipes if recipe.image_url or recipe.source == "MealMatch AI"]


def ai_recipe_is_coherent(recipe: Recipe) -> bool:
    """AI recipes saved before the dessert check ("Creamy Tomato Ice Cream Pie") stay hidden."""
    if recipe.source != "MealMatch AI":
        return True
    names = [item["name"] for item in recipe_ingredient_details(recipe)]
    return not savoury_ingredients_for_dessert(recipe.title or "", names)
