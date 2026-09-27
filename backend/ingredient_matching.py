"""Deterministic food-name matching for pantry availability, shopping and search.

Plain substring matching produced false positives that users noticed: pantry
"pepper" (a vegetable) satisfied "black pepper", "cherry" satisfied "cherry
tomato", "shrimp paste" counted as shrimp and "chicken stock" as chicken. This
module reduces each name to a small structure -- head food, identity modifiers,
variety modifiers and an optional derived product -- and compares those instead.

The rules mirror frontend/src/recipeFilters.ts so both sides agree.
Allergy and dietary safety checks deliberately keep their broader matching in
recommender.py: for safety a false positive is preferable to a miss.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

# Multi-word synonyms applied before tokenising (regex, replacement).
SYNONYMS: list[tuple[str, str]] = [
    (r"\b(?:green onions?|scallions?|spring onions?)\b", "springonion"),
    (r"\b(?:sweet corn|corn on the cob|corn kernels?)\b", "corn"),
    (r"\bcourgettes?\b", "zucchini"),
    (r"\baubergines?\b", "eggplant"),
    (r"\b(?:coriander leaves|fresh coriander|cilantro)\b", "cilantro"),
    (r"\bprawns?\b", "shrimp"),
    (r"\byoghurt\b", "yogurt"),
    (r"\b(?:chillies|chilies|chilli|chile|chiles)\b", "chili"),
    (r"\bgarbanzo(?: beans?)?\b", "chickpea"),
    (r"\bmayo\b", "mayonnaise"),
    (r"\bparmigiano(?: reggiano)?\b", "parmesan"),
    (r"&", " and "),
]

DESCRIPTORS = {
    "fresh", "freshly", "chopped", "sliced", "diced", "minced", "ground", "large", "small", "medium",
    "big", "organic", "grass", "fed", "free", "range", "boneless", "skinless", "lean", "extra",
    "virgin", "raw", "ripe", "frozen", "canned", "tinned", "dried", "whole", "halved", "peeled",
    "crushed", "finely", "roughly", "thinly", "cubed", "grated", "shredded", "cooked", "uncooked",
    "leftover", "plain", "unsalted", "salted", "low", "fat", "nonfat", "skim", "skimmed", "full",
    "reduced", "sodium", "mini", "of", "a", "the", "to", "taste", "for", "serving", "optional",
    "pinch", "handful", "bunch", "heavy", "double", "single", "light", "whipped", "whipping",
    "softened", "melted", "beaten", "packed", "fine", "coarse", "baby", "young", "new", "wild",
    "boiled", "roasted", "toasted", "smoked", "and", "or", "into", "about", "some", "few",
}
# Cuts and shapes: dropped when another word identifies the food.
PARTS = {
    "breast", "thigh", "drumstick", "wing", "leg", "fillet", "filet", "loin", "sirloin", "tenderloin",
    "flank", "chop", "cutlet", "shank", "rib", "brisket", "cube", "chunk", "piece", "strip", "slice",
    "ring", "wedge", "head", "stalk", "stick", "floret", "leaf", "sprig", "clove", "steak", "mince",
    "segment", "half", "quarter",
}
# Products made from a food. They change what the ingredient is.
DERIVED = {
    "stock", "broth", "bouillon", "sauce", "paste", "powder", "oil", "flour", "extract", "essence",
    "seasoning", "flake", "vinegar", "syrup", "jam", "jelly", "puree", "ketchup", "juice", "zest",
    "chip", "crisp", "fry", "fries", "gravy", "dressing", "spread", "cube",
}
# A whole fruit can supply its own juice or zest.
DERIVABLE_FROM_WHOLE = {"juice", "zest"}
# Modifiers that change the food itself (coconut milk is not milk).
IDENTITY = {
    "sweet", "coconut", "almond", "oat", "soy", "peanut", "cashew", "sour", "cream", "ice",
    "cottage", "goat", "sesame", "rice", "kidney", "evaporated", "condensed", "powdered",
}
# Pantry entries too vague to satisfy a specific recipe ingredient.
GENERIC = {"vegetable", "fruit", "produce", "snack", "food", "mix", "ingredient", "spice", "herb", "grocery", "bar", "item"}
CHEESES = {
    "parmesan", "cheddar", "mozzarella", "feta", "brie", "halloumi", "ricotta", "gouda", "gruyere",
    "pecorino", "mascarpone", "camembert", "emmental", "provolone", "manchego", "stilton", "paneer",
}
PEPPER_WORDS = {"pepper", "peppercorn", "capsicum"}
# Words that on their own mean a chili; "thai" or "bird" only count next to one of these.
CHILI_TRIGGERS = {"chili", "jalapeno", "cayenne", "serrano", "habanero", "chipotle", "poblano"}
CHILI_TYPES = CHILI_TRIGGERS | {"thai", "bird", "scotch", "bonnet"}
BELL_WORDS = {"bell", "sweet", "red", "green", "yellow", "orange", "capsicum"}


def singular(word: str) -> str:
    if len(word) <= 3 or word.endswith(("ss", "us", "is")):
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("oes") or word.endswith(("shes", "ches", "xes", "zes")):
        return word[:-2]
    if word in {"leaves", "halves", "loaves"}:
        return {"leaves": "leaf", "halves": "half", "loaves": "loaf"}[word]
    if word.endswith("s"):
        return word[:-1]
    return word


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return value.lower().replace("-", " ")


@dataclass(frozen=True)
class FoodName:
    head: str
    derived: str | None
    identity: frozenset = field(default_factory=frozenset)
    varieties: frozenset = field(default_factory=frozenset)
    generic: bool = False
    words: tuple = ()


@lru_cache(maxsize=20000)  # names repeat constantly while ranking recipes
def analyse(name: str, context: str = "recipe") -> FoodName:
    """Reduce a food name to comparable parts. context is "recipe" or "pantry"."""
    text = _plain(name)
    for pattern, replacement in SYNONYMS:
        text = re.sub(pattern, replacement, text)
    tokens = [singular(word) for word in re.findall(r"[a-z]+", text)]
    tokens = [word for word in tokens if word not in DESCRIPTORS]
    derived = next((word for word in reversed(tokens) if word in DERIVED), None)
    if derived and len(tokens) > 1:
        tokens = [word for word in tokens if word != derived]
    elif derived and len(tokens) == 1:
        derived = None  # "oil" alone is simply oil
    if len(tokens) > 1:
        kept = [word for word in tokens if word not in PARTS]
        tokens = kept or tokens[-1:]
    if tokens in (["steak"], ["mince"]):
        tokens = ["beef"]  # on its own, steak or mince means beef
    if not tokens:
        return FoodName(head="", derived=derived)

    # Peppers: one word, three different foods.
    has_pepper = any(word in PEPPER_WORDS for word in tokens)
    if has_pepper or any(word in CHILI_TRIGGERS for word in tokens):
        chili = [word for word in tokens if word in CHILI_TYPES]
        if derived == "flake" or chili:
            head = "chili"
            varieties = frozenset(word for word in chili if word != "chili")
            tokens = [word for word in tokens if word not in PEPPER_WORDS and word not in CHILI_TYPES and word not in BELL_WORDS]
            return FoodName(head=head, derived=derived, varieties=varieties | frozenset(tokens), words=tuple(tokens))
        if has_pepper:
            if {"black", "white", "peppercorn"} & set(tokens):
                return FoodName(head="peppercorn", derived=derived)
            if BELL_WORDS & set(tokens):
                return FoodName(head="bellpepper", derived=derived)
            return FoodName(head="peppercorn" if context == "recipe" else "bellpepper", derived=derived)

    cheese_variety = next((word for word in tokens if word in CHEESES), None)
    if cheese_variety and tokens[-1] != "cheese":
        tokens = tokens + ["cheese"]
    head = tokens[-1]
    modifiers = set(tokens[:-1])
    identity = frozenset(word for word in modifiers if word in IDENTITY)
    varieties = frozenset(modifiers - identity)
    return FoodName(head=head, derived=derived, identity=identity, varieties=varieties,
                    generic=head in GENERIC, words=tuple(tokens))


def foods_match(recipe_food: FoodName, pantry_food: FoodName) -> bool:
    if not recipe_food.head or not pantry_food.head or recipe_food.head != pantry_food.head:
        return False
    if recipe_food.derived != pantry_food.derived:
        if not (recipe_food.derived in DERIVABLE_FROM_WHOLE and pantry_food.derived is None):
            return False
    if pantry_food.generic or recipe_food.generic:
        return recipe_food.words == pantry_food.words
    if recipe_food.identity != pantry_food.identity:
        return False
    if recipe_food.varieties and pantry_food.varieties and not (recipe_food.varieties & pantry_food.varieties):
        return False
    return True


@lru_cache(maxsize=100000)
def pantry_match(recipe_ingredient: str, pantry_ingredient: str) -> bool:
    """True when the pantry item can stand in for the recipe ingredient."""
    return foods_match(analyse(recipe_ingredient, "recipe"), analyse(pantry_ingredient, "pantry"))


def ingredient_is_food(ingredient: str, query: str) -> bool:
    """True when a recipe ingredient *is* the searched food (not a product of it)."""
    return foods_match(analyse(ingredient, "recipe"), analyse(query, "recipe"))
