"""Import educational-use recipes and real meal photos from TheMealDB.

Run from the backend directory:
    ./venv/bin/python sync_themealdb.py
"""

import json
import re

import requests

from database import SessionLocal
from models import Recipe, upgrade_database


API_ROOT = "https://www.themealdb.com/api/json/v1/1"
POPULAR_SEARCHES = [
    "chicken", "pasta", "lasagna", "tacos", "curry", "fried rice", "salmon",
    "pancakes", "french toast", "chili", "ramen", "pizza", "burrito", "burger",
    "carbonara", "pad thai", "butter chicken", "macaroni", "stir fry", "caesar",
    "risotto", "meatballs", "enchiladas", "noodles", "soup", "brownies",
]
IMPORT_LIMIT = 120


def parse_measurement(value: str) -> tuple[float, str]:
    cleaned = (value or "").strip().lower()
    fraction_values = {"¼": 0.25, "½": 0.5, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}

    for symbol, amount in fraction_values.items():
        if cleaned.startswith(symbol):
            return amount, cleaned[len(symbol):].strip() or "portion"

    mixed = re.match(r"^(\d+)\s+(\d+)/(\d+)\s*(.*)$", cleaned)
    if mixed:
        amount = float(mixed.group(1)) + float(mixed.group(2)) / float(mixed.group(3))
        return amount, mixed.group(4).strip() or "portion"

    fraction = re.match(r"^(\d+)/(\d+)\s*(.*)$", cleaned)
    if fraction:
        return float(fraction.group(1)) / float(fraction.group(2)), fraction.group(3).strip() or "portion"

    numeric = re.match(r"^(\d+(?:\.\d+)?)\s*(.*)$", cleaned)
    if numeric:
        return float(numeric.group(1)), numeric.group(2).strip() or "portion"

    return 1, cleaned or "portion"


def meal_ingredients(meal: dict) -> list[dict]:
    ingredients = []
    for index in range(1, 21):
        name = (meal.get(f"strIngredient{index}") or "").strip().lower()
        if not name:
            continue
        amount, unit = parse_measurement(meal.get(f"strMeasure{index}") or "")
        ingredients.append({"name": name, "amount": amount, "unit": unit})
    return ingredients


def estimate_time(instructions: str) -> tuple[int, int]:
    text = instructions.lower()
    explicit_minutes = [int(value) for value in re.findall(r"(\d+)\s*(?:minutes?|mins?)", text)]
    cooking_time = sum(explicit_minutes) if explicit_minutes else 25
    return 10, min(max(cooking_time, 10), 180)


def import_recipes() -> tuple[int, int]:
    database = SessionLocal()
    imported = 0
    skipped = 0

    try:
        seen_source_ids: set[str] = set()
        for search_term in POPULAR_SEARCHES:
            response = requests.get(f"{API_ROOT}/search.php", params={"s": search_term}, timeout=30)
            response.raise_for_status()
            for meal in response.json().get("meals") or []:
                source_id = str(meal.get("idMeal") or "")
                if not source_id or source_id in seen_source_ids:
                    continue
                seen_source_ids.add(source_id)
                if database.query(Recipe).filter(Recipe.source_id == source_id).first():
                    skipped += 1
                    continue

                details = meal_ingredients(meal)
                instructions = (meal.get("strInstructions") or "").strip()
                if not details or not instructions:
                    skipped += 1
                    continue

                prep_time, cooking_time = estimate_time(instructions)
                database.add(Recipe(
                    title=(meal.get("strMeal") or "Untitled meal").strip(),
                    ingredients=",".join(item["name"] for item in details),
                    ingredient_details=json.dumps(details),
                    instructions=instructions,
                    prep_time=prep_time,
                    cooking_time=cooking_time,
                    servings=2,
                    difficulty="Intermediate" if len(details) > 10 else "Beginner",
                    cuisine=(meal.get("strArea") or meal.get("strCategory") or "Global").strip(),
                    calories=0,
                    image_url=(meal.get("strMealThumb") or "").strip(),
                    source="TheMealDB",
                    source_id=source_id,
                ))
                imported += 1
                if imported >= IMPORT_LIMIT:
                    break
            if imported >= IMPORT_LIMIT:
                break

        database.commit()
        return imported, skipped
    finally:
        database.close()


if __name__ == "__main__":
    upgrade_database()
    added, already_present = import_recipes()
    print(f"Imported {added} TheMealDB recipes; skipped {already_present} existing or incomplete records.")
