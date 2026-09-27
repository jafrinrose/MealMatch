import requests
import json
import os
import re

from difflib import SequenceMatcher

from ingredient_matching import singular
from ollama_server import ensure_running
from receipt_parsing import (
    ReceiptLine,
    expand_abbreviations,
    items_sold,
    merge_into_detections,
    parse_receipt_lines,
)

OLLAMA_URL = os.getenv("MEALMATCH_OLLAMA_GENERATE_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("MEALMATCH_TEXT_MODEL", "llama3.2:3b")
RECEIPT_MODEL = os.getenv("MEALMATCH_RECEIPT_MODEL", OLLAMA_MODEL)


def deterministic_poultry_safety_answer(question: str) -> str | None:
    """Intercept two high-risk poultry questions before generative inference."""
    normalized = question.casefold().replace("°", " degrees ")
    if not re.search(r"\b(chicken|turkey|poultry)\b", normalized):
        return None
    if re.search(r"\b(wash|rinse)\b", normalized) and re.search(r"\b(raw|uncooked)\b", normalized):
        return (
            "Don't wash or rinse raw poultry. Splashes can spread harmful bacteria around the kitchen; "
            "cook it thoroughly and wash your hands, utensils, and work surfaces instead."
        )
    temperature_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:degrees\s*)?(celsius|fahrenheit|c|f)\b", normalized)
    if temperature_match:
        value = float(temperature_match.group(1))
        unit = temperature_match.group(2)
        is_celsius = unit in {"celsius", "c"}
        threshold = 74.0 if is_celsius else 165.0
        display_threshold = "74 degrees Celsius" if is_celsius else "165 degrees Fahrenheit"
        if value < threshold:
            return f"Not yet. Poultry should reach at least {display_threshold} in its thickest part before serving."
        return f"That meets the minimum of {display_threshold}; check the thickest part with a clean food thermometer."
    return None


def ask_ollama(
    prompt: str,
    json_mode: bool = False,
    schema: dict | None = None,
    options: dict | None = None,
    model: str | None = None,
) -> str:
    """
    Sends a prompt to the local Ollama model and returns the response.
    A JSON schema, when given, constrains the output to that structure.
    A server that cannot be reached is started (when local) and asked again once.
    """

    payload = {
        "model": model or OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if schema:
        payload["format"] = schema
    elif json_mode:
        payload["format"] = "json"
    if options:
        payload["options"] = options

    try:
        try:
            response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        except requests.exceptions.ConnectionError:
            if not ensure_running(OLLAMA_URL):
                raise
            response = requests.post(OLLAMA_URL, json=payload, timeout=120)

        if response.status_code == 404 and "not found" in response.text:
            return f"Ollama error: the model {payload['model']} is not installed. Run 'ollama pull {payload['model']}'."
        response.raise_for_status()
        data = response.json()

        return data.get("response", "No response generated.")

    except requests.exceptions.ConnectionError:
        return (
            "Ollama is not running. Start it with 'ollama serve' "
            f"and make sure {OLLAMA_MODEL} is installed."
        )

    except requests.exceptions.Timeout:
        return "Ollama took too long to respond. Try again."

    except Exception as error:
        return f"Ollama error: {str(error)}"


def cooking_assistant_question(
    recipe,
    question: str,
    current_step: int | None = None,
    step_details: list[dict] | None = None,
) -> str:
    """
    Uses Ollama as a cooking assistant for a selected recipe.
    """

    safety_answer = deterministic_poultry_safety_answer(question)
    if safety_answer:
        return safety_answer

    ordered_steps = step_details or []
    step_context = ""
    if ordered_steps:
        safe_index = min(max(current_step or 0, 0), len(ordered_steps) - 1)
        numbered_steps = "\n".join(
            f"{index + 1}. {step.get('instruction', '')} (about {step.get('minutes', 1)} minutes)"
            for index, step in enumerate(ordered_steps)
        )
        step_context = f"""
The user is currently on step {safe_index + 1} of {len(ordered_steps)}:
{ordered_steps[safe_index].get("instruction", "")}

Ordered cooking steps:
{numbered_steps}
"""

    prompt = f"""
You are MealMatch, a helpful cooking assistant.

The user is cooking this recipe:

Recipe title:
{recipe.title}

Ingredients:
{recipe.ingredients}

Instructions:
{recipe.instructions}

{step_context}

User question:
{question}

Answer clearly and practically. Keep the response short enough to be read aloud while cooking.
Use warm, conversational language and natural contractions. Avoid markdown, bullet points,
abbreviations, or long ingredient lists that would sound robotic through text-to-speech.
When the question concerns what to do now or next, use the current-step context above.
Do not claim to advance, finish, or cancel the cooking session; the application handles those commands.
Food-safety rules are hard constraints: poultry is not safe until its thickest
part reaches 74 degrees Celsius or 165 degrees Fahrenheit. Never recommend
washing or rinsing raw poultry because splashes can spread bacteria.
"""

    return ask_ollama(prompt)


def general_cooking_assistant_question(
    pantry_ingredients: list[str],
    dietary_restrictions: list[str],
    allergies: list[str],
    question: str,
) -> str:
    """Answer general questions without pretending the user started a recipe."""
    prompt = f"""
You are MealMatch, a helpful cooking and pantry assistant.
The user is NOT currently cooking a selected recipe. Never imply that they are.

Pantry ingredients: {", ".join(pantry_ingredients) or "none recorded"}
Dietary restrictions: {", ".join(dietary_restrictions) or "none"}
Allergies: {", ".join(allergies) or "none"}
User question: {question}

Give a concise, practical answer. Treat allergies and dietary restrictions as hard safety rules.
If suggesting a meal, use pantry ingredients where practical and clearly identify anything missing.
"""
    return ask_ollama(prompt)


NON_FOOD_TERMS = {
    "air freshener", "aluminium foil", "aluminum foil", "bag", "batteries", "battery", "bleach",
    "body wash", "candle", "cat food", "cat litter", "charcoal", "cleaner", "cling film",
    "conditioner", "deodorant", "detergent", "diaper", "dish soap", "dog food", "fabric softener",
    "floss", "gift card", "hand soap", "laundry", "light bulb", "litter", "lotion", "mouthwash",
    "napkin", "notebook", "paper towel", "pet food", "plastic wrap", "razor", "receipt",
    "sanitizer", "shampoo", "soap", "sponge", "tissue", "toilet paper", "toothbrush",
    "toothpaste", "towel", "trash bag", "vitamin", "washing liquid", "wipes", "ziploc",
}
# Words that describe the product's marketing or brand rather than the food.
RECEIPT_NAME_NOISE = {
    "artisan", "boneless", "classic", "fresh", "kirkland", "large", "loose", "natural", "organic",
    "original", "plain", "premium", "president", "président", "select", "signature", "skinless",
}
# A line naming only a cut ("B/S THIGHS") means chicken on grocery receipts.
POULTRY_CUTS = {"breast", "drumstick", "thigh", "wing"}
# Plural-looking foods that are not plurals.
UNCOUNTABLE_FOODS = {"asparagus", "couscous", "grits", "greens", "hummus", "molasses", "oats", "swiss"}
RECEIPT_BATCH_SIZE = 15


def receipt_schema(lines: list[ReceiptLine]) -> dict:
    """One required key per line number, so the model has to answer every line
    and cannot add lines of its own. It copies the receipt text, names the food
    and only then classifies it: deciding "food" before expanding an
    abbreviation marked baguettes as non-food. Units come from the receipt, not
    the model, whose unit guesses were mostly wrong."""
    answer = {
        "type": "object",
        "properties": {
            "receipt": {"type": "string"},
            "ingredient": {"type": "string"},
            "food": {"type": "boolean"},
        },
        "required": ["receipt", "ingredient", "food"],
    }
    keys = [str(line.number) for line in lines]
    return {"type": "object", "properties": {key: answer for key in keys}, "required": keys}


def is_non_food(text: str, ignore: frozenset[str] = frozenset()) -> bool:
    # Whole words only: "bag" must not block bagels or cabbage.
    return any(
        re.search(rf"\b{re.escape(term)}(?:s|es)?\b", text)
        for term in NON_FOOD_TERMS - ignore
    )


def receipt_prompt(lines: list[ReceiptLine]) -> str:
    listed = "\n".join(
        f"{line.number}. {line.text}" + (f" (means: {line.hint})" if line.hint else "")
        for line in lines
    )
    return f"""
You are MealMatch. Below are product lines from a grocery receipt, already separated
from prices, totals and quantities. Stores abbreviate heavily and OCR can misread
letters. The text after "means" expands the abbreviations and can be trusted.

Answer every line under its number with:
- receipt: the line's receipt text, copied.
- ingredient: the product in plain words, abbreviations expanded. Keep every word
  that says which food it is, such as its colour, fat level, variety, style or form.
  Remove only brand names, sizes, counts, codes and marketing words such as organic,
  artisan, premium, fresh or large. A line that names only a cut (thighs, breasts,
  wings, drumsticks) is chicken. Keep the product itself: olives are not olive oil
  and cream is not milk. Fix words that OCR misspelled.
- food: true for anything people eat or drink, including water, drinks and cooking
  ingredients; false for household, cleaning, laundry, personal-care, paper, pet,
  pharmacy and other non-food products.

One line is exactly one product. Never split a line into two ingredients and never
add products that are not listed.

Lines:
{listed}

Return JSON only.
""".strip()


def _clean_name_words(name: str) -> list[str]:
    name = re.sub(r"\S+ \(brand\)", " ", name.lower())
    words = [word.strip(".,:;()") for word in name.split()]
    words = [word for word in words if word and not re.search(r"\d", word)]
    return [word for word in words if word not in RECEIPT_NAME_NOISE]


def _words_covered(words: list[str], by: list[str]) -> bool:
    """Every word appears in `by`, allowing for plurals and one-letter OCR slips."""
    targets = [singular(word) for word in by]
    return all(
        any(SequenceMatcher(None, singular(word), target).ratio() >= 0.85 for target in targets)
        for word in words
    )


def final_receipt_name(model_name: str, line: ReceiptLine) -> str:
    """
    The model's name, unless it merely dropped words from the receipt line: then
    the receipt's own words are kept, so whole and skim milk or red and yellow
    onions stay separate ingredients instead of collapsing into one.
    """

    words = _clean_name_words(model_name)
    receipt_words = _clean_name_words(line.hint or line.text)
    if not words or (receipt_words and _words_covered(words, receipt_words)):
        words = receipt_words
    if len(words) == 1 and singular(words[0]) in POULTRY_CUTS:
        words = ["chicken", *words]
    if words and words[-1] not in UNCOUNTABLE_FOODS:
        words[-1] = singular(words[-1])
    return " ".join(words)


def _name_receipt_batch(lines: list[ReceiptLine]) -> dict[int, dict] | None:
    """Ask the model about one batch of lines. None when it gave no usable answer."""
    response = ask_ollama(
        receipt_prompt(lines),
        schema=receipt_schema(lines),
        # About 34 tokens per line are needed; the cap stops a runaway string.
        options={"temperature": 0, "seed": 7, "num_predict": 64 * len(lines) + 64},
        model=RECEIPT_MODEL,
    )
    payload = _extract_json_object(response)
    if not payload:
        return None
    answers: dict[int, dict] = {}
    for line in lines:
        item = payload.get(str(line.number))
        if not isinstance(item, dict):
            continue
        ingredient = final_receipt_name(str(item.get("ingredient", "")), line)
        answers[line.number] = {
            "food": item.get("food") is True and 0 < len(ingredient) <= 60,
            "ingredient": ingredient,
        }
    return answers


def extract_receipt_items(raw_text_lines: list[str]) -> dict:
    """
    Turns receipt OCR lines into confirmation rows.

    Code finds the product lines, stated quantities and abbreviations; Ollama only
    names and classifies each numbered line; repeated purchases are then merged
    into one row with the quantity added up.
    """

    lines = parse_receipt_lines(raw_text_lines)
    warnings: list[str] = []
    answers: dict[int, dict] = {}
    unanswered = 0

    for start in range(0, len(lines), RECEIPT_BATCH_SIZE):
        batch = lines[start : start + RECEIPT_BATCH_SIZE]
        batch_answers = _name_receipt_batch(batch)
        # A reply that skipped some lines gets one retry for those; an unreachable
        # model does not, so an outage does not double the wait.
        if batch_answers is not None and len(batch_answers) < len(batch):
            skipped = [line for line in batch if line.number not in batch_answers]
            batch_answers.update(_name_receipt_batch(skipped) or {})
        for line in batch:
            if batch_answers is None or line.number not in batch_answers:
                unanswered += 1
                answers[line.number] = {"food": True, "ingredient": final_receipt_name("", line)}
            else:
                answers[line.number] = batch_answers[line.number]

    if unanswered:
        warnings.append(
            "The language model did not answer for every line, so some names come straight "
            "from the receipt and non-food items may be included. Please check them."
        )

    kept = {}
    for line in lines:
        answer = answers.get(line.number)
        if not answer or not answer["food"]:
            continue
        # The denylist backs up the model: check its name and what the receipt says
        # (except "bag", which receipts also use for bagged produce).
        if is_non_food(answer["ingredient"]) or is_non_food(expand_abbreviations(line.text), ignore=frozenset({"bag"})):
            continue
        kept[line.number] = answer

    stated_total = items_sold(raw_text_lines)
    units_read = sum(line.count for line in lines)
    if stated_total and units_read < stated_total:
        missing = stated_total - units_read
        warnings.append(
            f"The receipt says {stated_total} items were sold but {units_read} were read. "
            f"Add the missing {'item' if missing == 1 else f'{missing} items'} below if they are food."
        )

    return {"detections": merge_into_detections(lines, kept), "warnings": warnings}


def _extract_json_object(response: str) -> dict | None:
    try:
        payload = json.loads(response)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None


def generate_recipe_from_pantry(pantry_ingredients: list[str], user_request: str) -> dict | None:
    prompt = f"""
You are MealMatch, a careful recipe developer. Create one coherent, appetising recipe
that answers the user's request. The request defines the dish, cuisine and main ingredients.
The pantry foods below were pre-selected because they suit this kind of dish. They are
OPTIONS, never a checklist: use the ones that belong, skip any that would be odd, and do
not add other leftover foods.

The ingredient list must be COMPLETE: list every ingredient the dish genuinely needs,
including its base (rice for a biryani, pasta for a pasta dish), aromatics, spices,
fats and liquids, even when they are not in the pantry; the shopping list covers them.
A real recipe usually has 7 to 14 ingredients.

Pantry foods that suit this dish: {", ".join(pantry_ingredients) or "none - choose normal ingredients"}
Request: {user_request}

Return valid JSON only with this structure:
{{
  "title": "Recipe title",
  "cuisine": "Cuisine",
  "difficulty": "Beginner, Intermediate, or Advanced",
  "prep_time": 10,
  "cooking_time": 20,
  "servings": 2,
  "calories": 400,
  "ingredients": [
    {{"name": "ingredient", "amount": 1, "unit": "cup"}}
  ],
  "steps": [
    {{"instruction": "Detailed first instruction.", "minutes": 8}},
    {{"instruction": "Detailed second instruction.", "minutes": 15}}
  ]
}}

The title must name the requested dish or a well-known version of it: a request for ice cream
gets an ice cream dessert, not a pie or a savoury snack. Keep sweet and savoury apart: a dessert
never contains onion, garlic, tomato, potato, chili, meat or fish, and a savoury dish gets no
dessert toppings. If the request names dishes to avoid, give a different title and a dish that
differs in its main ingredients or method, not only in its name.

Use numeric ingredient amounts. Include at least four clear, safe, ordered steps. Give each step
its own realistic duration; preparation, simmering, baking and serving steps should not all have
the same duration. Treat every dietary restriction and allergy in the request as a hard rule.
Do not include markdown.
"""
    response = ask_ollama(prompt, json_mode=True)
    if response.startswith(("Ollama is not running", "Ollama took too long", "Ollama error")):
        raise RuntimeError(response)
    payload = _extract_json_object(response)

    required = {"title", "cuisine", "ingredients", "steps"}
    if not isinstance(payload, dict) or not required.issubset(payload):
        return None
    if not isinstance(payload["ingredients"], list) or not isinstance(payload["steps"], list):
        return None
    return payload


def select_pantry_for_dish(request: str, pantry_ingredients: list[str]) -> list[str]:
    """Ask the text model which listed pantry foods belong in the requested dish."""
    if not pantry_ingredients:
        return []
    prompt = f"""
A cook asked for: {request}
Pantry foods: {", ".join(pantry_ingredients)}

Which of these pantry foods would a skilled chef actually put in that dish? Choose only
foods that clearly belong; leave out anything that would be odd in it. Choose at most eight.
Return JSON only: {{"ingredients": ["exact pantry name", "..."]}}
"""
    payload = _extract_json_object(ask_ollama(prompt, json_mode=True)) or {}
    chosen = payload.get("ingredients", []) if isinstance(payload.get("ingredients"), list) else []
    lookup = {name.lower(): name for name in pantry_ingredients}
    return [lookup[str(name).strip().lower()] for name in chosen if str(name).strip().lower() in lookup]


def _model_substitutes(ingredients: list[str], pantry_ingredients: list[str], dietary_restrictions: list[str],
                       allergies: list[str], recipe_title: str, recipe_ingredients: list[str]) -> dict[str, list[dict]]:
    """Ask the text model for swaps; its answers keyed by the ingredient names asked about."""
    prompt = f"""
You are MealMatch. Suggest practical cooking substitutes for each listed ingredient of this recipe.
Recipe: {recipe_title or "a home-cooked dish"}
All recipe ingredients: {", ".join(recipe_ingredients) or "not given"}
Ingredients to replace: {", ".join(ingredients)}
Ingredients already in the pantry: {", ".join(pantry_ingredients) or "none"}
Dietary restrictions: {", ".join(dietary_restrictions) or "none"}
Allergies: {", ".join(allergies) or "none"}

Give up to three substitutes per ingredient that work in THIS dish, pantry foods first. The reason
says how to use it (amount or method) in under 15 words. Never suggest anything that conflicts with
an allergy or dietary restriction, and never the ingredient itself.
Return JSON only: {{"substitutions":[{{"ingredient":"exact name from the list","suggestions":[{{"name":"substitute","reason":"how to use it"}}]}}]}}
"""
    payload = _extract_json_object(ask_ollama(prompt, json_mode=True)) or {}
    groups = payload.get("substitutions") if isinstance(payload.get("substitutions"), list) else []
    from ingredient_matching import analyse

    answers: dict[str, list[dict]] = {}
    for index, group in enumerate(group for group in groups if isinstance(group, dict)):
        suggestions = [item for item in group.get("suggestions", []) if isinstance(item, dict)]
        named = str(group.get("ingredient", "")).strip().lower()
        # The model sometimes renames an ingredient ("fresh basil leaves" -> "basil"): match by food, then by order.
        target = next((item for item in ingredients if item.lower() == named), None)
        target = target or next((item for item in ingredients if named and analyse(item).head == analyse(named).head), None)
        target = target or (ingredients[index] if index < len(ingredients) and not named else None)
        if target and target not in answers:
            answers[target] = suggestions
    return answers


def suggest_ingredient_substitutes(
    missing_ingredients: list[str],
    pantry_ingredients: list[str],
    dietary_restrictions: list[str],
    allergies: list[str],
    recipe_title: str = "",
    recipe_ingredients: list[str] | None = None,
) -> list[dict]:
    """Swaps for each ingredient: the pantry and common kitchen swaps first (substitutions.py),
    and the text model only for ingredients those do not cover well."""
    if not missing_ingredients:
        return []
    from recommender import allergy_conflicts, dietary_conflict
    from substitutions import swaps_for

    def is_safe(name: str) -> bool:
        return (
            not allergy_conflicts([name], allergies)
            and dietary_conflict([name], dietary_restrictions) is None
        )

    known = {ingredient: swaps_for(ingredient, pantry_ingredients, is_safe) for ingredient in missing_ingredients}
    unclear = [ingredient for ingredient, swaps in known.items() if len(swaps) < 3]
    from_model = (
        _model_substitutes(unclear, pantry_ingredients, dietary_restrictions, allergies, recipe_title, recipe_ingredients or [])
        if unclear else {}
    )
    return [
        {
            "ingredient": ingredient.strip().lower(),
            "suggestions": swaps_for(ingredient, pantry_ingredients, is_safe, from_model.get(ingredient)) if ingredient in from_model else known[ingredient],
        }
        for ingredient in missing_ingredients
    ]
