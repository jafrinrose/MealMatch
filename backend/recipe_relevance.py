"""Choose which pantry ingredients belong in a requested dish.

The recipe model used to receive the whole pantry and, despite instructions, often
used it all (a biryani with kiwi, brie and asparagus). Now only ingredients that
fit the request are offered:

1. pantry foods the user named ("a quick chicken dinner" -> chicken);
2. pantry foods that commonly appear in reference recipes for the same kind of dish,
   measured across the curated recipe collection (TheMealDB), not generated data;
3. when the request names no food or dish, the foods closest to expiry, so the
   model builds a coherent dish around a few of them instead of all of them.

The same scores are used after generation to reject recipes that still pull in
pantry foods with no connection to the dish.

Desserts are handled apart (user testing, round 2): "ice cream" was split into
"ice" and "cream", savoury reference dishes made with cream matched, and the
model was offered onion, tomato and potato for an ice cream ("Creamy Tomato Ice
Cream Pie"). Compound foods now stay one term, and a sweet request is compared
only with sweet reference dishes and is never offered savoury pantry foods.

A request can also ask for a taste without naming a dish (design iteration 3):
"a sweet dish with what I have in my pantry" read "sweet" as filler, so the
model was offered the beef that expired first and wrote "Sweet Beef and Carrot
Fritters". A taste word now sets what the dish must taste like, unless it is part
of a food's name ("sweet potato", "sweet chilli") or the request names a savoury
food ("sweet and sour chicken"). With no dish named, a sweet request is offered
the sweet foods that most need using plus the dessert basics the pantry holds.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from ingredient_matching import SYNONYMS, analyse, ingredient_is_food, pantry_match, singular

# Words that describe the occasion or constraints rather than the food.
NOISE = {
    "a", "an", "the", "and", "or", "with", "without", "no", "for", "of", "to", "in", "on", "my", "me", "i",
    "want", "like", "make", "cook", "something", "some", "any", "please", "can", "you", "give", "idea",
    "quick", "quickly", "easy", "simple", "fast", "healthy", "light", "hearty", "cheap", "budget", "tonight",
    "dinner", "lunch", "breakfast", "brunch", "supper", "meal", "dish", "recipe", "food", "snack", "minute",
    "min", "hour", "under", "oven", "stove", "pan", "pot", "one", "two", "family", "kid", "friendly",
    "weeknight", "comfort", "tasty", "delicious", "nice", "good", "new", "different", "version", "using",
    "use", "up", "what", "have", "got", "fridge", "pantry", "ingredient", "leftover", "left", "over", "it",
    "that", "this", "is", "be", "are", "from", "just", "really", "very", "spicy", "mild", "sweet", "savory",
    "savoury", "vegetarian", "vegan", "gluten", "free", "dairy", "keto", "low", "carb", "high", "protein",
}
FOOD_FAMILY_WORDS = {
    "pasta": {"spaghetti", "penne", "macaroni", "linguine", "fettuccine", "lasagne", "lasagna", "pasta"},
    "seafood": {"shrimp", "fish", "salmon", "tuna", "crab", "mussel", "squid"},
    "fish": {"fish", "salmon", "tuna", "cod", "haddock", "mackerel"},
    "meat": {"beef", "pork", "lamb", "chicken"},
}


# Request words that name a whole pantry category ("a fruit smoothie").
CATEGORY_WORDS = {
    "fruit": "fruit", "berry": "fruit", "vegetable": "vegetables", "veggie": "vegetables", "veg": "vegetables",
    "salad": "vegetables", "seafood": "seafood", "meat": "meat", "dairy": "dairy", "cheese": "dairy",
}
FRUIT_HEADS = {"apple", "banana", "berry", "strawberry", "blueberry", "raspberry", "blackberry", "cherry", "grape", "kiwi",
               "mango", "melon", "watermelon", "orange", "peach", "pear", "pineapple", "plum", "date", "fig", "lemon", "lime"}


def _category(item) -> str:
    head = analyse(item.ingredient, "pantry").head
    if head in {"tomato", "avocado", "cucumber", "eggplant", "bellpepper", "chili", "olive"}:
        return "vegetables"  # botanically fruit, but cooked as vegetables
    if head in FRUIT_HEADS:
        return "fruit"
    value = (getattr(item, "category", "") or "").lower()
    return {"produce": "vegetables", "protein": "meat"}.get(value, value)


# Foods named with a modifier that changes what they are ("ice cream" is not
# cream). The two words stay one term, so they never match separately.
COMPOUND_HEADS = {"cream", "milk", "butter", "potato", "sauce", "cheese", "noodle", "flour", "yogurt", "oil", "paste", "bean", "sugar"}
COMPOUND_MODIFIERS = {"ice", "sour", "sweet", "coconut", "almond", "oat", "soy", "peanut", "cashew", "cottage", "goat", "sesame", "rice", "cream", "condensed", "evaporated"}

# Dishes that are always sweet. "pie", "tart" and "pancake" can be savoury, so
# they only count next to a sweet food ("apple pie").
SWEET_DISHES = {
    "ice cream", "dessert", "cake", "cupcake", "brownie", "cookie", "pudding", "sundae", "sorbet", "gelato",
    "mousse", "cheesecake", "crumble", "muffin", "waffle", "smoothie", "milkshake", "parfait", "trifle",
    "fudge", "custard", "tiramisu", "doughnut", "donut", "meringue", "popsicle", "affogato", "chocolate",
    "caramel", "sweet treat", "treat", "compote", "granola",
    "browny", "cooky", "smoothy",  # how singular() reads "brownies", "cookies", "smoothies"
}
SOMETIMES_SWEET = {"pie", "tart", "pancake", "crepe", "toast", "bread", "bar"}
SWEET_FOODS = FRUIT_HEADS | {"chocolate", "custard", "honey", "jam", "berry", "vanilla", "caramel", "cinnamon", "sugar", "syrup", "nutella"}

# Foods that do not belong in a dessert unless the cook asks for them.
SAVOURY_FOODS = {
    "onion", "springonion", "shallot", "leek", "garlic", "tomato", "potato", "cucumber", "lettuce", "cabbage",
    "kale", "spinach", "broccoli", "cauliflower", "celery", "asparagus", "eggplant", "zucchini", "bellpepper",
    "chili", "jalapeno", "peppercorn", "mushroom", "olive", "kimchi", "pickle", "pea", "bean", "lentil",
    "chicken", "beef", "pork", "lamb", "turkey", "bacon", "ham", "sausage", "mince", "steak", "salami",
    "fish", "salmon", "tuna", "cod", "shrimp", "crab", "lobster", "mussel", "squid", "anchovy", "sardine",
    "stock", "broth", "mustard", "cumin", "soy", "carrot", "avocado", "feta", "brie", "cheddar",
    "parmesan", "halloumi", "gouda", "pecorino", "mayonnaise", "ketchup", "vinegar", "sirloin", "thigh",
}
# Reference dishes are sweet when they use one of these and none of SAVOURY_FOODS.
SWEET_MARKERS = {"sugar", "chocolate", "cocoa", "vanilla", "jam", "syrup", "honey", "icing", "custard", "caramel", "marshmallow", "meringue"}

# Words that ask for a taste rather than name a food or a dish.
TASTE_WORDS = {"sweet": "sweet", "sugary": "sweet", "savoury": "savoury", "savory": "savoury", "salty": "savoury"}
# Request words that ask for any dessert rather than a particular one.
ANY_DESSERT = {"dessert", "treat", "sweet treat", "sweets"}


def _tokens(request: str) -> list[str]:
    return [singular(word) for word in re.findall(r"[a-z]+", request.lower())]


def request_terms(request: str) -> list[str]:
    """Food and dish words in a request, keeping compound foods ("ice cream") whole."""
    tokens = _tokens(request)
    terms: list[str] = []
    index = 0
    while index < len(tokens):
        word = tokens[index]
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        if word in COMPOUND_MODIFIERS and following in COMPOUND_HEADS:
            terms.append(f"{word} {following}")
            index += 2
            continue
        if word not in NOISE and len(word) > 2:
            terms.append(word)
        index += 1
    return terms


def _asked_tastes(request: str) -> set[str]:
    """Taste words that describe the dish, not a food's name ("sweet potato", "sweet chilli")."""
    text = request.lower()
    for pattern, replacement in SYNONYMS:
        text = re.sub(pattern, replacement, text)  # "sweet corn" is corn
    tokens = [singular(word) for word in re.findall(r"[a-z]+", text)]
    tastes = set()
    for index, word in enumerate(tokens):
        if word not in TASTE_WORDS:
            continue
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        if following in COMPOUND_HEADS or (following and is_savoury_food(following)):
            continue
        tastes.add(TASTE_WORDS[word])
    return tastes


def request_flavour(request: str) -> str | None:
    """"sweet" or "savoury" when the request settles what the dish tastes like, else None."""
    tokens = _tokens(request)
    terms = request_terms(request)
    tastes = _asked_tastes(request)
    if "savoury" in tastes:
        return "savoury"
    if set(terms) & SWEET_DISHES or any(f"{a} {b}" in SWEET_DISHES for a, b in zip(tokens, tokens[1:])):
        return "sweet"
    if set(tokens) & SOMETIMES_SWEET and set(tokens) & SWEET_FOODS:
        return "sweet"
    # "Something sweet" is a dessert; "sweet and sour chicken" is a savoury dish with a sweet sauce.
    if "sweet" in tastes and not any(is_savoury_food(term) for term in terms):
        return "sweet"
    return None


def is_sweet_request(request: str) -> bool:
    return request_flavour(request) == "sweet"


def _food_words(name: str, context: str = "pantry") -> set[str]:
    food = analyse(name, context)
    return {food.head, *food.words, *(food.varieties or ()), *([food.derived] if food.derived else [])}


def is_savoury_food(name: str, context: str = "pantry") -> bool:
    words = _food_words(name, context)
    if "sweet" in analyse(name, context).identity:
        return False  # sweet potato, sweet corn: at home in some desserts
    return bool(words & SAVOURY_FOODS)


def is_sweet_food(name: str, context: str = "pantry") -> bool:
    """Fruit, chocolate, honey and ready-made desserts: foods that make a dish sweet."""
    words = _food_words(name, context)
    tokens = set(_tokens(name))
    return bool(
        words & (SWEET_FOODS | SWEET_MARKERS)
        or tokens & SWEET_DISHES
        or any(f"{a} {b}" in SWEET_DISHES for a, b in zip(_tokens(name), _tokens(name)[1:]))
    )


def is_dessert_food(name: str, context: str = "pantry") -> bool:
    """Sweet foods that belong only in desserts (ice cream, cookies, chocolate syrup), not fruit or honey."""
    tokens = _tokens(name)
    return bool(set(tokens) & (SWEET_DISHES | {"syrup", "icing", "candy", "marshmallow", "sprinkle", "nutella"})
                or any(f"{a} {b}" in SWEET_DISHES for a, b in zip(tokens, tokens[1:])))


def is_sweet_reference(recipe) -> bool:
    ingredients = [part.strip() for part in (recipe.ingredients or "").split(",") if part.strip()]
    words = set()
    for ingredient in ingredients:
        words |= _food_words(ingredient, "recipe")
    return bool(words & SWEET_MARKERS) and not any(is_savoury_food(ingredient, "recipe") for ingredient in ingredients)


def savoury_ingredients_for_dessert(request: str, recipe_ingredients: list[str]) -> list[str]:
    """Savoury ingredients in a recipe made for a sweet request, unless the request named them."""
    if not is_sweet_request(request):
        return []
    named = set(request_terms(request))
    return [
        name for name in recipe_ingredients
        if is_savoury_food(name, "recipe") and not (_food_words(name, "recipe") & named)
    ]


def dessert_ingredients_for_savoury(request: str, recipe_ingredients: list[str]) -> list[str]:
    """Dessert foods in a recipe the cook asked to be savoury, unless the request named them."""
    if request_flavour(request) != "savoury":
        return []
    named = set(request_terms(request))
    return [
        name for name in recipe_ingredients
        if is_dessert_food(name, "recipe") and not (_food_words(name, "recipe") & named)
    ]


def lacks_sweetness(request: str, recipe_ingredients: list[str]) -> bool:
    """A recipe for a sweet request with nothing sweet in it (no fruit, sugar, honey or chocolate)."""
    return is_sweet_request(request) and not any(is_sweet_food(name, "recipe") for name in recipe_ingredients)


# "with what I have", "from my fridge", "use up": the cook wants to shop as little as possible.
PANTRY_ONLY = re.compile(
    r"\b(what (?:i|we) (?:have|'?ve got|got)|(?:in|from|with|using) (?:my|our|the) (?:pantry|fridge|kitchen|cupboard)"
    r"|pantry only|only (?:use|what)|use up|leftovers?|without (?:shopping|buying))\b"
)
# Basics most kitchens keep; a pantry-only recipe may still call for them.
KITCHEN_STAPLES = {"salt", "peppercorn", "sugar", "flour", "oil", "butter", "water", "ice", "vanilla", "cinnamon", "baking", "soda", "yeast", "cornstarch", "cornflour", "spice", "herb", "nutmeg"}


def wants_pantry_only(request: str) -> bool:
    return bool(PANTRY_ONLY.search(request.lower().replace("\u2019", "'")))


def ingredients_to_buy(recipe_ingredients: list[str], pantry_names: list[str]) -> list[str]:
    """Recipe ingredients that are neither in the pantry nor a kitchen staple."""
    return [
        name for name in recipe_ingredients
        if not any(pantry_match(name, pantry_name) for pantry_name in pantry_names)
        and not (_food_words(name, "recipe") & KITCHEN_STAPLES)
        and analyse(name).derived not in {"extract", "powder", "essence"}
    ]


def title_foods_missing(title: str, recipe_ingredients: list[str], pantry_names: list[str]) -> list[str]:
    """Pantry foods the title names but the ingredient list leaves out ("Banana Date Bites" with neither)."""
    title_words = set(_tokens(title))
    missing = set()
    for name in pantry_names:
        food = analyse(name, "pantry")
        if not food.head or food.generic or food.head not in title_words:
            continue
        if not any(analyse(ingredient).head == food.head or pantry_match(ingredient, name) for ingredient in recipe_ingredients):
            missing.add(food.head)
    return sorted(missing)


def _days_to_expiry(value: str | None) -> int | None:
    try:
        return (datetime.fromisoformat(str(value)).date() - date.today()).days
    except (TypeError, ValueError):
        return None


def _is_usable(name: str) -> bool:
    food = analyse(name, "pantry")
    return bool(food.head) and not food.generic


def _urgency(item) -> tuple[bool, int]:
    days = _days_to_expiry(item.expiry_date)
    return (days is None, days if days is not None else 0)


def _not_expired(item) -> bool:
    days = _days_to_expiry(item.expiry_date)
    return days is None or days >= 0


def _fits_flavour(name: str, flavour: str | None) -> bool:
    if flavour == "sweet":
        return not is_savoury_food(name)
    if flavour == "savoury":
        return not is_dessert_food(name)
    return True


def _names_any_dessert(request: str) -> bool:
    """A sweet request that names no particular dish or food ("something sweet", "a dessert")."""
    return is_sweet_request(request) and not set(request_terms(request)) - ANY_DESSERT


def _dessert_scores(pantry_items, reference_recipes) -> dict[str, float]:
    """How well each pantry food suits a dessert: its share of sweet reference dishes,
    and at least 0.5 for foods that are sweet themselves. Savoury foods score 0."""
    references = [
        [part.strip() for part in (recipe.ingredients or "").split(",") if part.strip()]
        for recipe in reference_recipes if is_sweet_reference(recipe)
    ]
    scores = {}
    for item in pantry_items:
        name = item.ingredient
        if not _is_usable(name):
            continue
        if is_savoury_food(name):
            scores[name] = 0.0
            continue
        hits = sum(any(pantry_match(ingredient, name) for ingredient in ingredients) for ingredients in references)
        share = hits / len(references) if references else 0.0
        scores[name] = round(max(share, 0.5) if is_sweet_food(name) else share, 3)
    return scores


def _dessert_from_pantry(pantry_items, scores: dict[str, float], limit: int) -> list[str]:
    """The sweet foods that most need using, then the dessert basics the pantry has, one entry per food."""
    seen: set[str] = set()

    def first_of_its_kind(name: str) -> bool:  # "blueberries" and "blueberry" are one food
        head = analyse(name, "pantry").head
        if head in seen:
            return False
        seen.add(head)
        return True

    usable = [item for item in pantry_items if scores.get(item.ingredient, 0) > 0 and _not_expired(item)]
    sweet = [
        item.ingredient for item in sorted(usable, key=_urgency)
        if is_sweet_food(item.ingredient) and first_of_its_kind(item.ingredient)
    ][:6]
    basics = [
        item.ingredient for item in sorted(usable, key=lambda item: -scores[item.ingredient])
        if not is_sweet_food(item.ingredient) and scores[item.ingredient] >= 0.12 and first_of_its_kind(item.ingredient)
    ]
    return (sweet + basics)[:limit]


def score_pantry_relevance(request: str, pantry_items, reference_recipes) -> dict[str, float]:
    """Score 0..1 for how well each pantry ingredient fits the request."""
    terms = request_terms(request)
    term_set = set(terms)
    for family, members in FOOD_FAMILY_WORDS.items():
        if family in term_set:
            term_set |= members
    names = [item.ingredient for item in pantry_items if _is_usable(item.ingredient)]
    scores = {name: 0.0 for name in names}
    if _names_any_dessert(request):
        return {**scores, **_dessert_scores(pantry_items, reference_recipes)}
    if not term_set:
        return scores
    phrases = {term for term in term_set if " " in term}
    words = term_set - phrases
    flavour = request_flavour(request)
    sweet = flavour == "sweet"

    wanted_categories = {CATEGORY_WORDS[word] for word in words if word in CATEGORY_WORDS}
    mentioned = {
        item.ingredient for item in pantry_items
        if item.ingredient in scores and (
            analyse(item.ingredient, "pantry").head in words
            or any(pantry_match(phrase, item.ingredient) for phrase in phrases)
            or _category(item) in wanted_categories
        )
    }

    # Reference dishes like the request: title words count double, named foods count once.
    # A dessert is compared only with sweet dishes, so cream in a curry says nothing about ice cream.
    candidates = [recipe for recipe in reference_recipes if is_sweet_reference(recipe)] if sweet else reference_recipes
    ranked = []
    for recipe in candidates:
        title = " ".join(singular(word) for word in re.findall(r"[a-z]+", (recipe.title or "").lower()))
        title_words = set(title.split())
        ingredients = [part.strip() for part in (recipe.ingredients or "").split(",") if part.strip()]
        ingredient_words = {word for ingredient in ingredients for word in analyse(ingredient).words}
        overlap = (
            2 * len(title_words & words) + len(ingredient_words & words)
            + sum(2 * (phrase in title) + any(ingredient_is_food(ingredient, phrase) for ingredient in ingredients) for phrase in phrases)
        )
        if overlap:
            ranked.append((overlap, id(recipe), ingredients))
    ranked.sort(key=lambda entry: entry[0], reverse=True)
    references = [ingredients for _, _, ingredients in ranked[:30]]
    if sweet and len(references) < 5:
        # Few dishes name this dessert: what desserts in general use is the next best guide.
        used = {key for _, key, _ in ranked[:30]}
        references += [
            [part.strip() for part in (recipe.ingredients or "").split(",") if part.strip()]
            for recipe in candidates if id(recipe) not in used
        ][: 30 - len(references)]

    for name in names:
        if name in mentioned:
            scores[name] = 1.0
            continue
        if not _fits_flavour(name, flavour):
            continue
        if references:
            hits = sum(any(pantry_match(ingredient, name) for ingredient in ingredients) for ingredients in references)
            scores[name] = round(hits / len(references), 3)
    return scores


def choose_pantry_for_request(request: str, pantry_items, reference_recipes, limit: int = 10, selector=None) -> tuple[list[str], dict[str, float]]:
    """Return the pantry ingredients to offer the recipe model, plus every score."""
    scores = score_pantry_relevance(request, pantry_items, reference_recipes)
    flavour = request_flavour(request)
    if _names_any_dessert(request):
        # "Something sweet with what I have": build it on the sweet food that needs using first.
        chosen = _dessert_from_pantry(pantry_items, scores, limit)
        if chosen:
            return chosen, scores
    chosen = [name for name, score in sorted(scores.items(), key=lambda entry: entry[1], reverse=True) if score >= 0.12][:limit]
    if chosen:
        return chosen, scores
    if request_terms(request) and selector is not None:
        # A dish the reference collection does not know: let the text model pick
        # from the pantry list only, then keep names that really are in the pantry.
        usable_names = [item.ingredient for item in pantry_items if _is_usable(item.ingredient)]
        picked = [
            name for name in selector(request, usable_names)
            if name in scores and _fits_flavour(name, flavour)
        ][:limit]
        if picked:
            return picked, {**scores, **{name: 1.0 for name in picked}}
    # No food or dish named: anchor on the food that needs using first and add only
    # the pantry foods that commonly go with it, keeping to the taste asked for.
    usable = [item for item in pantry_items if _is_usable(item.ingredient) and _not_expired(item) and _fits_flavour(item.ingredient, flavour)]
    usable.sort(key=_urgency)
    if not usable:
        return [], scores
    anchor = usable[0].ingredient
    anchor_scores = score_pantry_relevance(analyse(anchor, "pantry").head, pantry_items, reference_recipes)
    partners = [name for name, score in sorted(anchor_scores.items(), key=lambda entry: entry[1], reverse=True)
                if name != anchor and score >= 0.15 and _fits_flavour(name, flavour)][: limit - 1]
    chosen = [anchor, *partners]
    return chosen, {**scores, **{name: max(anchor_scores.get(name, 0), 0.5) for name in chosen}}


# Everyday aromatics and fats fit almost any savoury dish; never flag them as unrelated.
STAPLES = {"onion", "garlic", "oil", "butter", "salt", "peppercorn", "lemon", "lime", "ginger", "herb"}


def unrelated_pantry_ingredients(recipe_ingredients: list[str], offered: list[str], scores: dict[str, float], pantry_names: list[str]) -> list[str]:
    """Pantry foods the recipe uses although they were not offered and scored as unrelated."""
    unrelated = []
    for pantry_name in pantry_names:
        if pantry_name in offered or scores.get(pantry_name, 0) >= 0.12 or not _is_usable(pantry_name):
            continue
        if analyse(pantry_name, "pantry").head in STAPLES:
            continue
        if any(pantry_match(ingredient, pantry_name) for ingredient in recipe_ingredients):
            unrelated.append(pantry_name)
    return unrelated
