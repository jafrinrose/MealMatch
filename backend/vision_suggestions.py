"""Turn the vision model's raw answers into reviewable pantry suggestions.

The model's JSON is untrusted. On a crowded photo it can be cut off mid-item or
loop on the same items; it can use units the confirmation form cannot show;
and it can name the brand instead of the food. Every rule here is plain code,
like receipt_parsing.py, so it can be tested without the model. The design
history is in docs/user-testing-round-2-results.md (photo detection
iteration 1).
"""

from __future__ import annotations

import json
import os
import re

from ingredient_matching import IDENTITY, singular


# Consecutive items that only repeat earlier names before the answer counts as a loop.
REPEAT_LIMIT = 3

# The confirmation form's units (quantityUnits in frontend/src/App.tsx). Any
# other unit was shown as "piece", so the model's "package" for grapes or
# "loaf" for bread reached the user as "1 piece".
UNIT_ALIASES = {
    "piece": "piece", "item": "piece", "whole": "piece", "each": "piece", "unit": "piece",
    "fruit": "piece", "head": "piece", "fillet": "piece", "portion": "piece",
    "box": "box", "tub": "box", "container": "box", "punnet": "box", "clamshell": "box", "case": "box",
    "pack": "pack", "packet": "pack", "package": "pack", "pkg": "pack", "pouch": "pack",
    "sachet": "pack", "wrapper": "pack", "tray": "pack", "loaf": "pack",
    "carton": "carton", "bottle": "bottle", "jug": "bottle", "can": "can", "tin": "can", "jar": "jar",
    "bag": "bag", "sack": "bag", "bunch": "bunch",
    "g": "g", "gram": "g", "kg": "kg", "kilogram": "kg", "ml": "ml", "l": "l", "litre": "l", "liter": "l",
}
PLURAL_UNITS = {
    "piece": "pieces", "box": "boxes", "pack": "packs", "carton": "cartons", "bottle": "bottles",
    "can": "cans", "jar": "jars", "bag": "bags", "bunch": "bunches",
}

# Brand and store names read from packaging. They say who made the food, not
# what it is, so "meiji milk" and "milk" are the same pantry item.
BRAND_NAMES = (
    "a2", "anchor", "arla", "ayam brand", "barilla", "bega", "cadbury", "campbell's", "chobani",
    "coles", "danone", "del monte", "dole", "dutch lady", "fairprice", "fair price", "farmers union",
    "ferrero", "gardenia", "godiva", "great value", "heinz", "hershey's", "hersheys", "kellogg's",
    "kelloggs", "kirkland", "knorr", "kraft", "lindt", "lurpak", "magnolia", "marigold", "meiji",
    "nestle", "nestlé", "president", "quaker", "san remo", "sunshine", "tesco", "uncle tobys",
    "woolworths", "yoplait",
)
# Marketing words that do not change the food. "plain" is there because the
# prompt asks for a "plain food name" and the model sometimes copies the word
# ("plain bread", "plain milk").
MARKETING_WORDS = {"organic", "fresh", "premium", "original", "classic", "natural", "all-natural", "homestyle", "plain"}
# Vague names and copies of the prompt's own template text.
VAGUE_NAMES = {
    "canned food", "canned goods", "dairy product", "sauces", "packaged food", "packaged goods",
    "vegetables", "unspecified", "unknown", "food name", "plain food name",
}
# Product lines whose name stands for a food.
BRAND_FOODS = {
    "dairy milk": "chocolate", "kit kat": "chocolate", "kitkat": "chocolate", "nutella": "chocolate spread",
    "philadelphia": "cream cheese", "nescafe": "coffee", "nescafé": "coffee", "milo": "chocolate malt drink",
    "weet-bix": "cereal", "weetbix": "cereal", "vegemite": "yeast spread", "marmite": "yeast spread",
    "coca-cola": "cola", "coke": "cola", "pepsi": "cola", "oreo": "cookies", "pringles": "potato chips",
    "indomie": "instant noodles", "yakult": "probiotic drink",
}
# Spellings that name the same food, used only to compare names.
SAME_FOOD = {"chilli": "chili", "yoghurt": "yogurt", "capsicum": "pepper"}
# Merging "milk" into "chocolate milk" would lose a food, so these modifiers keep names apart.
DISTINCT_MODIFIERS = IDENTITY | {"chocolate"}

_BRAND_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(brand) for brand in BRAND_NAMES) + r")(?=\s|$)")


def salvage_items(raw: str) -> list[dict]:
    """Every complete item object in the answer, even when it stops mid-item.

    Parsing the whole answer as one JSON object threw away all items whenever
    the output limit cut the last item off, and the user saw no suggestions.
    """
    decoder, items = json.JSONDecoder(), []
    index = raw.find("[")
    while index >= 0:
        start = raw.find("{", index)
        if start < 0:
            break
        try:
            item, index = decoder.raw_decode(raw, start)
        except json.JSONDecodeError:
            break
        if isinstance(item, dict):
            items.append(item)
    return items


def is_repeating(items: list[dict], limit: int = REPEAT_LIMIT) -> bool:
    """True once the last `limit` items all repeat earlier names: the model is looping."""
    seen: set[str] = set()
    repeats = 0
    for item in items:
        name = clean_food_name(str(item.get("ingredient", "")))
        repeats = repeats + 1 if name in seen else 0
        seen.add(name)
    return repeats >= limit


def vision_model_display_name(model_name: str) -> str:
    """Return a stable user-facing name without hiding the evaluated model size."""
    if model_name.casefold().startswith("qwen2.5vl:"):
        size = model_name.split(":", 1)[1].upper()
        return f"Qwen2.5-VL {size}"
    return model_name


def form_unit(value: object) -> str:
    words = _words(str(value or ""))
    return UNIT_ALIASES.get(singular(words[0]) if words else "", "piece")


def _words(text: str) -> list[str]:
    return re.sub(r"[^\w\s&'-]", " ", text.lower()).split()


def _brand_food(text: str) -> str | None:
    lowered = " ".join(_words(text))
    return next(
        (food for phrase, food in BRAND_FOODS.items() if re.search(rf"\b{re.escape(phrase)}(?=\s|$)", lowered)),
        None,
    )


def clean_food_name(name: str, visible_text: str = "") -> str:
    """The food, without brand, store or marketing words.

    A product line in the name ("cadbury dairy milk chocolate") becomes its
    food. A product line on the label only counts when it agrees with the
    model's name: the label "Dairy Milk" turns "chocolate milk" into chocolate,
    but a label the model attached to the wrong item ("Nescafe" on a pepper)
    changes nothing.
    """
    food = _brand_food(name)
    if food:
        return food
    label_food = _brand_food(visible_text)
    if label_food and set(label_food.split()) & set(_words(name)):
        return label_food
    cleaned = _BRAND_PATTERN.sub(" ", " ".join(_words(name)))
    words = [word for word in cleaned.split() if word not in MARKETING_WORDS]
    return " ".join(words) or " ".join(_words(name))


def name_key(name: str) -> tuple[str, ...]:
    """The words of a name for comparison: singular, same spelling, no joining words."""
    return tuple(
        SAME_FOOD.get(singular(word), singular(word))
        for word in _words(name)
        if word not in {"&", "and", "of", "with"}
    )


def clean_qwen_items(items: object, model_name: str) -> list[dict]:
    """Validate untrusted VLM JSON before exposing suggestions for review."""
    cleaned: list[dict] = []
    blocked_terms = {
        "soap", "detergent", "cleaner", "bleach", "shampoo", "toothpaste",
        "sponge", "paper towel", "toilet paper", "bag only", "container",
    }
    if not isinstance(items, list):
        return cleaned
    for item in items:
        if not isinstance(item, dict):
            continue
        visible_text = str(item.get("visible_text", "")).strip()
        ingredient = clean_food_name(str(item.get("ingredient", "")), visible_text)
        if (
            not ingredient
            or ingredient in VAGUE_NAMES
            or any(term in ingredient for term in blocked_terms)
        ):
            continue
        try:
            confidence = min(1.0, max(0.0, float(item.get("confidence", 0))))
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < float(os.getenv("MEALMATCH_VLM_MIN_CONFIDENCE", "0.45")):
            continue
        try:
            count = max(1, round(float(item.get("quantity", 1))))
        except (TypeError, ValueError):
            count = 1
        unit = form_unit(item.get("unit"))
        cleaned.append(
            {
                "ingredient": ingredient,
                "quantity": f"{count} {PLURAL_UNITS.get(unit, unit) if count > 1 else unit}",
                "confidence": round(confidence, 3),
                "source": vision_model_display_name(model_name),
                "visible_text": visible_text,
                "category": str(item.get("category", "other")).strip().lower(),
            }
        )
    unique: dict[frozenset[str], dict] = {}
    for item in cleaned:
        key = frozenset(name_key(item["ingredient"]))
        current = unique.get(key)
        if current is None or item["confidence"] > current["confidence"]:
            unique[key] = item
    return list(unique.values())


def _covers(broader: tuple[str, ...], narrower: tuple[str, ...]) -> bool:
    """`broader` names the same food as `narrower` with more detail.

    The shorter name must keep the food word, which comes last: "pepper" is a
    bell pepper, but "chocolate" is not chocolate syrup and "walnuts" is not
    walnut bread. Modifiers that make a different food keep names apart.
    """
    wide, narrow = set(broader), set(narrower)
    return narrow < wide and broader[-1] in narrow and not (wide - narrow) & DISTINCT_MODIFIERS


class SuggestionMerger:
    """Combines the passes over one photo: the whole photo, then overlapping close-ups.

    A later pass often sees a food again, sometimes under a shorter or longer
    name. Only new foods are passed on. A less specific name ("pepper" after
    "bell pepper") is dropped; a more specific one is offered as an
    alternative name on the existing row.
    """

    def __init__(self, earlier: list[dict] | None = None) -> None:
        """`earlier` holds suggestions already shown, from a finished whole-photo pass."""
        self.accepted: list[tuple[dict, tuple[str, ...]]] = [(item, name_key(item["ingredient"])) for item in earlier or []]

    def add(self, items: list[dict]) -> tuple[list[dict], list[dict]]:
        earlier = list(self.accepted)
        new: list[dict] = []
        alternatives: list[dict] = []
        for item in items:
            key = name_key(item["ingredient"])
            if any(set(key) == set(known) or _covers(known, key) for _, known in earlier):
                continue
            broader = next((existing for existing, known in earlier if _covers(key, known)), None)
            if broader is not None:
                alternatives.append({"detection_id": broader["detection_id"], "ingredient": item["ingredient"]})
                continue
            item["detection_id"] = f"suggestion-{len(self.accepted) + 1}"
            self.accepted.append((item, key))
            new.append(item)
        return new, alternatives
