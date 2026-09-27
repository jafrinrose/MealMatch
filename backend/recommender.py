import faiss
import math
import numpy as np
import re
import threading
from datetime import date, datetime
from sentence_transformers import SentenceTransformer

from impact import RESCUE_WINDOW_DAYS
from ingredient_matching import analyse, pantry_match
from model_versions import EMBEDDING_MODEL, EMBEDDING_REVISION, MODEL_CACHE

embedding_model = None
embedding_model_unavailable = False
cached_index_signature = None
cached_index = None
cached_recipe_ids = []
# The startup warm-up and the first requests can load the model or build the index together.
_model_lock = threading.Lock()
_index_lock = threading.Lock()


def get_embedding_model():
    """Load the semantic model that setup_models.py downloads, at its pinned version.

    Without it, recommendations use pantry matching only.
    """
    global embedding_model, embedding_model_unavailable

    with _model_lock:
        if embedding_model is not None:
            return embedding_model

        if embedding_model_unavailable:
            return None

        try:
            embedding_model = SentenceTransformer(
                EMBEDDING_MODEL,
                revision=EMBEDDING_REVISION,
                cache_folder=str(MODEL_CACHE / "huggingface"),
                local_files_only=True,
            )
        except Exception:
            embedding_model_unavailable = True
            print("Semantic recipe matching is off: run 'python backend/setup_models.py' to download its model.")
            return None

        return embedding_model


def create_recipe_text(recipe):
    return f"""
    Recipe title: {recipe.title}
    Ingredients: {recipe.ingredients}
    Cuisine: {recipe.cuisine}
    Difficulty: {recipe.difficulty}
    Cooking time: {recipe.cooking_time} minutes
    """


def get_recipe_ingredients(recipe):
    return [
        ingredient.strip().lower()
        for ingredient in recipe.ingredients.split(",")
        if ingredient.strip()
    ]


def build_faiss_index(recipes):
    global cached_index_signature, cached_index, cached_recipe_ids
    model = get_embedding_model()

    if model is None:
        return None, []

    signature = tuple((recipe.id, recipe.title, recipe.ingredients) for recipe in recipes)
    with _index_lock:
        if cached_index is not None and signature == cached_index_signature:
            return cached_index, cached_recipe_ids

        recipe_texts = [create_recipe_text(recipe) for recipe in recipes]

        embeddings = model.encode(recipe_texts)
        embeddings = np.array(embeddings).astype("float32")

        index = faiss.IndexFlatL2(embeddings.shape[1])
        index.add(embeddings)

        recipe_ids = [recipe.id for recipe in recipes]

        cached_index_signature = signature
        cached_index = index
        cached_recipe_ids = recipe_ids

    return index, recipe_ids


def search_recipes(user_ingredients, recipes, top_k=20):
    """
    Semantic search using Sentence Transformers + FAISS.
    This retrieves semantically similar recipes, but exact ingredient
    scoring is handled later by the ranking function.
    """

    if not recipes:
        return []

    top_k = min(top_k, len(recipes))

    index, recipe_ids = build_faiss_index(recipes)

    if index is None:
        return []

    query_text = "User has these ingredients: " + ", ".join(user_ingredients)
    model = get_embedding_model()
    query_embedding = model.encode([query_text])
    query_embedding = np.array(query_embedding).astype("float32")

    _distances, indices = index.search(query_embedding, top_k)

    results = []

    for idx in indices[0]:
        recipe_id = recipe_ids[idx]
        recipe = next(recipe for recipe in recipes if recipe.id == recipe_id)
        results.append(recipe)

    return results


INGREDIENT_ALIASES = {
    "eggs": "egg",
    "tomatoes": "tomato",
    "grape tomato": "tomato",
    "green onions": "onion",
    "green onion": "onion",
    "yoghurt": "yogurt",
    "feta cheese crumble": "feta",
    "feta cheese": "feta",
    "chicken breast": "chicken",
    "chicken breasts": "chicken",
}

ALLERGEN_GROUPS = {
    "dairy": {
        "milk", "cheese", "butter", "cream", "yogurt", "feta", "mozzarella", "brie", "parmesan", "cheddar",
        "ghee", "ricotta", "mascarpone", "paneer", "halloumi", "gruyere", "gouda", "pecorino", "camembert",
        "emmental", "provolone", "manchego", "stilton", "burrata", "creme fraiche", "custard", "whey",
        "casein", "kefir", "quark", "labneh",
    },
    "gluten": {
        "bread", "pasta", "flour", "cereal", "noodle", "soy sauce", "tortilla", "bun", "spaghetti", "penne",
        "macaroni", "linguine", "fettuccine", "lasagne", "lasagna", "tagliatelle", "orzo", "couscous",
        "bulgur", "barley", "rye", "wheat", "semolina", "spelt", "farro", "cracker", "biscuit", "pastry",
        "wrap", "pita", "naan", "baguette", "croissant", "bagel", "muffin", "cake", "cookie", "beer",
        "seitan", "udon", "ramen", "panko", "graham", "digestive", "malt",
    },
    "egg": {"egg", "mayonnaise", "meringue"},
    "eggs": {"egg", "mayonnaise", "meringue"},
    "fish": {"fish", "salmon", "tuna", "cod", "anchovy", "sardine", "mackerel", "haddock", "trout", "tilapia", "halibut", "sea bass", "herring", "worcestershire"},
    "shellfish": {"shrimp", "prawn", "crab", "lobster", "mussel", "oyster", "clam", "scallop", "squid", "calamari", "octopus", "crayfish", "langoustine"},
    "peanuts": {"peanut", "peanuts", "peanut butter"},
    "tree nuts": {"almond", "cashew", "walnut", "pecan", "pistachio", "hazelnut", "macadamia", "brazil nut", "pine nut"},
    "soy": {"soy", "soy sauce", "tofu", "edamame", "miso", "tempeh"},
    "sesame": {"sesame", "tahini"},
}

MEAT = {
    "beef", "chicken", "ham", "lamb", "pork", "turkey", "bacon", "sausage", "chorizo", "salami", "pepperoni",
    "prosciutto", "pancetta", "guanciale", "gammon", "veal", "venison", "duck", "goose", "mutton", "rabbit",
    "mince", "sirloin", "brisket", "meatball", "oxtail", "suet", "gelatin", "gelatine", "bratwurst",
    "frankfurter", "hot dog", "kielbasa", "jerky", "bone broth",
}
SEAFOOD = ALLERGEN_GROUPS["fish"] | ALLERGEN_GROUPS["shellfish"] | {"caviar", "roe", "bonito", "dashi", "surimi", "fish sauce", "oyster sauce"}
PORK = {"pork", "ham", "bacon", "prosciutto", "pancetta", "guanciale", "chorizo", "salami", "pepperoni", "gammon", "gelatin", "gelatine"}
ALCOHOL = {"wine", "beer", "rum", "brandy", "whisky", "whiskey", "vodka", "liqueur", "sherry", "bourbon", "cognac", "sake", "mirin"}
KETO_EXCLUSIONS = {"bread", "pasta", "flour", "cereal", "noodle", "rice", "potato", "sugar", "honey", "tortilla", "oat", "couscous", "quinoa", "syrup", "lentil", "chickpea", "banana"}
PALEO_EXCLUSIONS = KETO_EXCLUSIONS | ALLERGEN_GROUPS["dairy"] | {"bean", "lentil", "tofu", "soy", "peanut"}

# Names that contain a blocked word without being that food ("peanut butter" is
# not butter). Without these, dairy-free and gluten-free users lost many
# suitable recipes, which matters now that diet rules are hard filters.
LOOKALIKES = {
    "butter": ("peanut butter", "almond butter", "cashew butter", "nut butter", "cocoa butter", "apple butter", "butternut", "butter bean", "butterhead", "vegan butter", "plant butter"),
    "milk": ("coconut milk", "almond milk", "oat milk", "soy milk", "rice milk", "cashew milk", "plant milk", "vegan milk"),
    "cream": ("coconut cream", "cream of tartar", "vegan cream", "oat cream", "soy cream"),
    "cheese": ("vegan cheese", "plant cheese"),
    "yogurt": ("coconut yogurt", "soy yogurt", "oat yogurt", "almond yogurt", "vegan yogurt"),
    "flour": ("rice flour", "almond flour", "coconut flour", "corn flour", "cornflour", "chickpea flour", "buckwheat flour", "tapioca flour", "potato flour", "gluten free flour"),
    "wheat": ("buckwheat",),
    "noodle": ("rice noodle", "glass noodle", "zucchini noodle", "shirataki"),
    "pasta": ("gluten free pasta", "rice pasta", "chickpea pasta", "lentil pasta"),
    "bread": ("gluten free bread",),
    "tortilla": ("corn tortilla",),
    "soy sauce": ("tamari", "gluten free soy sauce"),
    "wrap": ("lettuce wrap",),
    "cake": ("rice cake",),
    "wine": ("wine vinegar",),
    "sausage": ("vegetarian sausage", "vegan sausage", "plant based sausage"),
    "mince": ("vegetarian mince", "vegan mince", "soy mince", "quorn mince", "mincemeat"),
}


def canonical_ingredient(value):
    cleaned = " ".join(value.strip().lower().replace("-", " ").split())
    return INGREDIENT_ALIASES.get(cleaned, cleaned[:-1] if cleaned.endswith("s") and len(cleaned) > 4 else cleaned)


def ingredient_is_match(recipe_ingredient, pantry_ingredient):
    """Can this pantry item stand in for the recipe ingredient? (see ingredient_matching)"""
    return pantry_match(recipe_ingredient, pantry_ingredient)


def loose_ingredient_match(first, second):
    """Broad substring match, kept for allergy and diet safety where a miss is worse than a false alarm."""
    first_value = canonical_ingredient(first)
    second_value = canonical_ingredient(second)
    return (
        first_value == second_value
        or (len(first_value) > 3 and first_value in second_value)
        or (len(second_value) > 3 and second_value in first_value)
    )


def ingredient_contains_any(ingredients, blocked_terms):
    return any(blocked_terms_in(ingredient, blocked_terms) for ingredient in ingredients)


def blocked_terms_in(ingredient, blocked_terms):
    """The blocked terms this ingredient contains, ignoring look-alike names."""
    normalized = canonical_ingredient(ingredient)
    plain = " ".join(ingredient.lower().replace("-", " ").split())
    found = []
    for term in blocked_terms:
        blocked = canonical_ingredient(term)
        if not (loose_ingredient_match(normalized, blocked) or re.search(rf"\b{re.escape(blocked)}\b", normalized)):
            continue
        if any(lookalike in plain for lookalike in LOOKALIKES.get(blocked, ())):
            continue
        found.append(term)
    return found


def expiry_days(expiry_date):
    if not expiry_date:
        return None
    try:
        parsed = datetime.fromisoformat(expiry_date).date()
    except ValueError:
        return None
    return (parsed - date.today()).days


DIET_EXCLUSIONS = {
    "vegan": MEAT | SEAFOOD | ALLERGEN_GROUPS["dairy"] | {"egg", "honey", "mayonnaise", "meringue"},
    "vegetarian": MEAT | SEAFOOD,
    "pescatarian": MEAT,
    "dairy-free": ALLERGEN_GROUPS["dairy"],
    "gluten-free": ALLERGEN_GROUPS["gluten"],
    "keto": KETO_EXCLUSIONS,
    "paleo": PALEO_EXCLUSIONS,
    "halal": PORK | ALCOHOL,
    "kosher": PORK | ALLERGEN_GROUPS["shellfish"],
}
# The same rules in words for the recipe model, which ignores a bare "vegan".
DIET_RULES = {
    "vegan": "no meat, poultry, fish, seafood, eggs, honey, gelatin or dairy (milk, butter, cheese, cream, yogurt)",
    "vegetarian": "no meat, poultry, fish or seafood",
    "pescatarian": "no meat or poultry",
    "dairy-free": "no milk, butter, cheese, cream, yogurt or ghee",
    "gluten-free": "no wheat, flour, bread, pasta, noodles, couscous, barley, rye or soy sauce",
    "keto": "no bread, pasta, rice, potato, sugar, honey, oats, grains, lentils or chickpeas",
    "paleo": "no grains, dairy, beans, lentils, soy, peanuts or sugar",
    "halal": "no pork, gelatin or alcohol",
    "kosher": "no pork or shellfish",
}


def dietary_conflict(recipe_ingredients, restrictions):
    """The first saved diet this recipe breaks, as "<diet> preference", or None."""
    for restriction in sorted({item.lower() for item in restrictions}):
        blocked = DIET_EXCLUSIONS.get(restriction)
        if blocked and ingredient_contains_any(recipe_ingredients, blocked):
            return f"{restriction} preference"
    return None


def dietary_conflict_reason(recipe_ingredients, restrictions):
    """Which diets a recipe breaks and the ingredients responsible, for the recipe card."""
    reasons = []
    for restriction in sorted({item.lower() for item in restrictions}):
        blocked = DIET_EXCLUSIONS.get(restriction)
        if not blocked:
            continue
        culprits = [ingredient for ingredient in recipe_ingredients if blocked_terms_in(ingredient, blocked)]
        if culprits:
            reasons.append({"diet": restriction, "ingredients": culprits[:3]})
    return reasons


def allergy_conflicts(recipe_ingredients, allergies):
    conflicts = []
    for allergy in allergies:
        normalized = canonical_ingredient(allergy)
        blocked = ALLERGEN_GROUPS.get(allergy.lower(), {normalized})
        if ingredient_contains_any(recipe_ingredients, blocked):
            conflicts.append(allergy)
    return sorted(set(conflicts))


def urgency_weight(days_left):
    """1 for food that expires today, falling to about 0.17 at the edge of the use-soon window."""
    return (RESCUE_WINDOW_DAYS + 1 - days_left) / (RESCUE_WINDOW_DAYS + 1)


def calculate_personalized_score(
    recipe,
    pantry_items,
    ingredient_ratings,
    dietary_restrictions,
    allergies,
    preferred_cuisines,
    max_cooking_time=None,
    semantic_score=0.5,
):
    """Score a recipe for this pantry: using food before it expires comes first.

    Expired pantry food no longer counts as available. "Use soon" is the same
    0-5 day window as the home screen and the waste-impact record; food closer to
    its date weighs more. Allergy conflicts score 0. Diet conflicts are scored
    too, so they can be shown after every recipe that fits the diet has run out,
    but they are never eligible.
    """
    recipe_ingredients = get_recipe_ingredients(recipe)
    available = [item for item in pantry_items if (expiry_days(item.expiry_date) or 0) >= 0]
    matched_ingredients = []
    missing_ingredients = []

    for ingredient in recipe_ingredients:
        if any(ingredient_is_match(ingredient, item.ingredient) for item in available):
            matched_ingredients.append(ingredient)
        else:
            missing_ingredients.append(ingredient)

    allergy_hits = allergy_conflicts(recipe_ingredients, allergies)
    diet_conflict = dietary_conflict(recipe_ingredients, dietary_restrictions)
    eligible = not allergy_hits and diet_conflict is None
    ingredient_match_score = len(matched_ingredients) / max(len(recipe_ingredients), 1)

    use_soon = [
        (item, expiry_days(item.expiry_date)) for item in available
        if expiry_days(item.expiry_date) is not None and expiry_days(item.expiry_date) <= RESCUE_WINDOW_DAYS
    ]
    used_soon = []
    seen_foods = set()
    for item, days in sorted(use_soon, key=lambda entry: entry[1]):
        # "avocado" and "avocados" in the pantry are one food, not two rescues.
        food = analyse(item.ingredient, "pantry")
        key = (food.head, food.identity, food.derived)
        if key in seen_foods or not any(ingredient_is_match(ingredient, item.ingredient) for ingredient in recipe_ingredients):
            continue
        seen_foods.add(key)
        used_soon.append((item, days))
    expiring_matched = [item.ingredient for item, _ in used_soon]
    # Grows with every use-soon food the recipe uses, most for food due first, and
    # levels off gently so recipes stay comparable when most of the pantry is due.
    rescue_score = 1 - math.exp(-sum(urgency_weight(days) for _, days in used_soon) / 1.5)

    cuisines = [item.strip().lower() for item in preferred_cuisines if item.strip()]
    cuisine_match = any(
        preference in (recipe.cuisine or "").lower() or (recipe.cuisine or "").lower() in preference
        for preference in cuisines
    )
    cuisine_score = 1 if cuisine_match else (0.5 if not cuisines else 0)
    cooking_time_score = 1 if not max_cooking_time or recipe.cooking_time <= max_cooking_time else 0.25

    relevant_ratings = [
        ingredient_ratings[canonical_ingredient(ingredient)]
        for ingredient in recipe_ingredients
        if canonical_ingredient(ingredient) in ingredient_ratings
    ]
    preference_score = (
        max(0, min(1, (sum(relevant_ratings) / len(relevant_ratings) + 5) / 10))
        if relevant_ratings else 0.5
    )

    if use_soon:
        weighted = 0.50 * rescue_score + 0.40 * ingredient_match_score + 0.06 * cuisine_score + 0.04 * cooking_time_score
    else:
        weighted = 0.90 * ingredient_match_score + 0.06 * cuisine_score + 0.04 * cooking_time_score
    final_score = weighted if not allergy_hits and ingredient_match_score > 0 else 0

    reasons = []
    if expiring_matched:
        reasons.append(f"uses {', '.join(expiring_matched)} before it expires")
    if matched_ingredients:
        reasons.append(f"matches {len(matched_ingredients)} of {len(recipe_ingredients)} pantry ingredients")
    if cuisine_match:
        reasons.append(f"fits your {recipe.cuisine} cuisine preference")
    if max_cooking_time and recipe.cooking_time <= max_cooking_time:
        reasons.append(f"fits your {max_cooking_time}-minute cooking limit")

    explanation = (
        f"Recommended because it {' and '.join(reasons)}. "
        f"You only need {len(missing_ingredients)} more ingredient{'s' if len(missing_ingredients) != 1 else ''}."
        if reasons else "This recipe uses ingredients already available in your pantry."
    )

    return {
        "final_score": round(final_score, 3),
        "ingredient_match_score": round(ingredient_match_score, 3),
        "expiry_score": round(rescue_score, 3),
        "rescue_score": round(rescue_score, 3),
        "preference_score": round(preference_score, 3),
        "cuisine_score": round(cuisine_score, 3),
        "cooking_time_score": cooking_time_score,
        "semantic_score": round(semantic_score, 3),
        "matched_ingredients": sorted(matched_ingredients),
        "missing_ingredients": sorted(missing_ingredients),
        "expiring_matched_ingredients": expiring_matched,
        "use_soon_used": [{"ingredient": item.ingredient, "days_left": days} for item, days in used_soon],
        "allergy_conflicts": allergy_hits,
        "dietary_conflict": diet_conflict,
        "diet_conflicts": dietary_conflict_reason(recipe_ingredients, dietary_restrictions) if diet_conflict else [],
        "eligible": eligible,
        "explanation": explanation,
    }


def recommendation_sort_key(score_details):
    """Diet-fitting recipes first, then recipes that use food due soon, then the weighted score."""
    return (
        score_details["dietary_conflict"] is None,
        bool(score_details["expiring_matched_ingredients"]),
        score_details["final_score"],
        score_details["rescue_score"],
        score_details["ingredient_match_score"],
        len(score_details["matched_ingredients"]),
        score_details["cuisine_score"],
        score_details["semantic_score"],
    )
