"""How much of a pantry item a cooked meal uses, in the pantry item's own unit.

The pantry used to change only when the recipe and the pantry used the same
unit ("2 pieces" of egg from "12 pieces"). Most pairs differ: "1 cup" of milk
against "1 bottle", "2 cloves" against "1 piece" of garlic, "200 g" of potato
against "4 pieces". Those items never changed, so after "Meal is ready" the
pantry looked untouched (user testing, round 2).

Amounts are converted through grams with typical piece weights and package
sizes. They are estimates: every quantity stays editable in the pantry, and an
amount that cannot be converted is left unchanged rather than guessed.
"""
from __future__ import annotations

import re

from impact import TYPICAL_GRAMS
from ingredient_matching import analyse, singular

# Grams (or millilitres, taken as equal) in one unit.
MEASURES = {
    "g": 1, "gram": 1, "kg": 1000, "kilogram": 1000, "mg": .001,
    "ml": 1, "millilitre": 1, "milliliter": 1, "cl": 10, "dl": 100, "l": 1000, "litre": 1000, "liter": 1000,
    "cup": 240, "tbsp": 15, "tablespoon": 15, "tbs": 15, "tblsp": 15, "tbls": 15, "tsp": 5, "teaspoon": 5,
    "oz": 28, "ounce": 28, "lb": 454, "pound": 454,
    "pinch": .5, "dash": 1, "sprinkling": 2, "splash": 10, "drizzle": 10, "knob": 15, "handful": 30,
}
# Units that mean "this many of the food".
COUNTS = {
    "", "piece", "whole", "large", "medium", "small", "portion", "serving", "item", "unit", "fruit",
    "chopped", "sliced", "diced", "beaten", "halved", "finely", "roughly", "thinly", "peeled", "crushed",
    "minced", "grated", "cubed", "juice", "zest", "fillet", "breast", "thigh", "leg", "head", "stalk", "sprig",
}
# Recipe amounts that use almost nothing, in grams.
TRACE = {"to taste": .5, "to serve": 5, "garnish": 2, "for frying": 10, "as required": 2, "as needed": 2, "for greasing": 2}
PACKAGES = {
    "carton": 1000, "bottle": 750, "box": 400, "pack": 400, "packet": 200, "package": 400, "bag": 500,
    "jar": 350, "can": 400, "tin": 400, "tub": 500, "punnet": 250, "bunch": 100, "loaf": 400, "tray": 400,
    "pouch": 200, "sachet": 20, "container": 400, "case": 400,
}
UNIT_ALIASES = {"pc": "piece", "pcs": "piece", "tbl": "tbsp", "t": "tsp", "lbs": "lb", "kgs": "kg", "gm": "g", "gms": "g"}
VOLUMES = {"ml", "millilitre", "milliliter", "cl", "dl", "l", "litre", "liter", "cup", "tbsp", "tablespoon", "tbs", "tblsp", "tbls", "tsp", "teaspoon", "splash", "drizzle", "dash"}
# Grams per millilitre for foods much lighter or heavier than water (a cup of spinach is about 30 g).
DENSITY = [
    (r"spinach|lettuce|kale|rocket|salad|herb|basil|parsley|cilantro|coriander|mint", .12),
    (r"flour|cocoa", .53), (r"sugar", .83), (r"\boat|granola|cereal|breadcrumb|panko", .38),
    (r"rice|couscous|quinoa|lentil", .77), (r"pasta|macaroni|noodle", .42), (r"cheese|parmesan", .42),
    (r"berr|cherr|grape", .62), (r"almond|nut|walnut|cashew|pecan|chocolate", .6),
    (r"onion|pepper|carrot|celery|tomato|mushroom|potato|cucumber|zucchini|broccoli", .6),
]

# Typical contents of one package of a food, in grams (first match wins).
PACKAGE_GRAMS = [
    (r"ice cream", 500), (r"milk|juice|kefir", 1000), (r"cream", 300), (r"yog", 500), (r"butter", 250),
    (r"cheese|brie|feta|parmesan|mozzarella|halloumi", 200), (r"berr|cherr|grape|tomato", 250),
    (r"spinach|lettuce|salad|herb|basil|parsley|cilantro|kale|rocket", 150),
    (r"rice|pasta|spaghetti|noodle|flour|sugar|oat|couscous|quinoa|lentil|cereal|granola", 500),
    (r"bread|baguette|loaf", 400), (r"oil|sauce|vinegar|syrup|honey", 500), (r"chocolate", 100),
    (r"cookie|biscuit|cracker", 200), (r"almond|nut|walnut|cashew|pecan", 200),
    (r"kimchi|jalapeno|olive|pickle", 300), (r"shrimp|prawn|salmon|fish|chicken|beef|pork|lamb|mince", 400),
]
# Foods sold as a package of countable pieces.
PIECES_PER_PACKAGE = [(r"egg", 12), (r"wrap|tortilla|pita", 8), (r"bagel|bun|roll|muffin", 6)]
# A pantry "piece" of garlic is a bulb of about ten cloves.
GARLIC_CLOVES_PER_BULB = 10


def unit_name(unit: str) -> str:
    """The unit a free-text amount is measured in: "tablespoons chopped" -> "tablespoon"."""
    text = str(unit or "").strip().lower()
    for phrase in TRACE:
        if text.startswith(phrase):
            return phrase
    match = re.search(r"[a-z]+", text)
    word = match.group(0) if match else ""
    word = UNIT_ALIASES.get(word, word)
    if word in MEASURES or word in PACKAGES:
        return word
    word = singular(word)
    if word in {"clove", "slice"}:
        return word
    word = UNIT_ALIASES.get(word, word)
    return word if word in MEASURES or word in PACKAGES else "piece" if word in COUNTS else word


def grams_per_piece(food: str) -> float:
    if analyse(food, "pantry").head == "garlic":
        return 50  # a bulb
    return next((grams for pattern, grams in TYPICAL_GRAMS if re.search(pattern, food.lower())), 120)


def _density(food: str) -> float:
    return next((grams for pattern, grams in DENSITY if re.search(pattern, food.lower())), 1.0)


def _package_grams(food: str, unit: str) -> float:
    return next((grams for pattern, grams in PACKAGE_GRAMS if re.search(pattern, food.lower())), PACKAGES[unit])


def _pieces_per_package(food: str) -> int | None:
    return next((count for pattern, count in PIECES_PER_PACKAGE if re.search(pattern, food.lower())), None)


def amount_in_pantry_unit(food: str, recipe_amount: float, recipe_unit: str, pantry_unit: str) -> float | None:
    """How many pantry units ("bottle", "piece", "g"...) the recipe amount uses, or None if unknown."""
    source, target = unit_name(recipe_unit), unit_name(pantry_unit)
    garlic = analyse(food, "pantry").head == "garlic"
    if source == "clove" or (garlic and source == "piece" and target == "piece"):
        # Recipes count garlic in cloves, the pantry in bulbs.
        if target == "piece" and garlic:
            return recipe_amount / GARLIC_CLOVES_PER_BULB
        source, recipe_amount = "g", recipe_amount * 5
    if source == target:
        return recipe_amount
    if target in PACKAGES and source == "piece" and _pieces_per_package(food):
        return recipe_amount / _pieces_per_package(food)

    if source in MEASURES:
        grams = recipe_amount * MEASURES[source] * (_density(food) if source in VOLUMES else 1)
    elif source in TRACE:
        grams = TRACE[source]
    elif source == "slice":
        grams = recipe_amount * 30
    elif source == "piece" or source in PACKAGES:
        pieces = recipe_amount * (_pieces_per_package(food) or 1) if source in PACKAGES else recipe_amount
        grams = pieces * grams_per_piece(food) if source == "piece" else recipe_amount * _package_grams(food, source)
    else:
        return None

    if target in MEASURES:
        return grams / MEASURES[target] / (_density(food) if target in VOLUMES else 1)
    if target == "piece":
        return grams / grams_per_piece(food)
    if target in PACKAGES:
        return grams / _package_grams(food, target)
    return None


def remaining_amount(have: float, used: float, pantry_unit: str) -> float:
    """What is left, rounded the way the pantry shows it; 0 means used up."""
    left = max(0.0, have - used)
    unit = unit_name(pantry_unit)
    if unit in MEASURES and unit not in {"cup", "kg", "l", "lb"}:
        return float(round(left))
    # Pieces and packages in tenths: less than a twentieth left counts as used up.
    step = .05 if unit in {"kg", "l", "lb"} else .1
    return round(round(left / step) * step, 2)


def display_unit(amount: float, unit: str) -> str:
    """"pieces" becomes "piece" once one or less is left."""
    word = unit.strip()
    if amount <= 1 and word.lower().endswith("s") and unit_name(word) in {"piece", *PACKAGES}:
        return singular(word.lower())
    return word
