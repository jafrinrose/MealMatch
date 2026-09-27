"""Ingredient swaps: the cook's own pantry first, then common kitchen swaps, then the text model.

User testing (design iteration 3) found Swap often answering "No reliable substitute
was found". Swaps were worked out only for the ingredients the cook was missing, all
in one model call, and only the model's answer was used. So an ingredient already in
the pantry never had swaps, one the model skipped or renamed ("fresh basil leaves"
came back as "basil") matched nothing, and a busy or stopped model left every
ingredient empty.

Now each ingredient is looked up on its own, when the cook taps Swap:

1. pantry foods of the same kind (feta for cheddar, red onion for shallot);
2. a table of standard kitchen substitutions, marked "in pantry" when the cook has one;
3. the text model, told the dish, only when those give fewer than three swaps.

Every suggestion is checked against saved allergies and diets.
"""
from __future__ import annotations

from ingredient_matching import analyse, pantry_match

# Standard substitutions, keyed by what analyse() calls the food. Each entry is
# (substitute, how to use it).
KITCHEN_SWAPS: dict[str, list[tuple[str, str]]] = {
    # Dairy and eggs
    "butter": [("olive oil", "Use about three quarters as much; best in savoury cooking."), ("coconut oil", "Same amount; works in baking."), ("margarine", "Same amount.")],
    "milk": [("oat milk", "Same amount."), ("soy milk", "Same amount; the closest in protein."), ("water and a little butter", "For sauces and batters, 1 cup water with 1 tbsp butter.")],
    "cream": [("milk and melted butter", "3/4 cup milk with 1/4 cup melted butter per cup; will not whip."), ("coconut cream", "Same amount; adds a light coconut taste."), ("plain yogurt", "Stir in off the heat so it does not split.")],
    "sour cream": [("plain yogurt", "Same amount; Greek yogurt is thickest."), ("cream cheese", "Thin with a little milk.")],
    "yogurt": [("sour cream", "Same amount."), ("buttermilk", "Thinner; use a little less.")],
    "buttermilk": [("milk and lemon juice", "1 tbsp lemon juice in 1 cup milk, left for 5 minutes."), ("plain yogurt", "Thin with a little milk.")],
    "oil": [("vegetable oil", "Same amount."), ("butter", "Same amount, melted.")],
    "olive oil": [("vegetable oil", "Same amount."), ("butter", "Same amount, melted; richer.")],
    "egg": [("flax egg", "1 tbsp ground flaxseed with 3 tbsp water per egg, for baking."), ("mashed banana", "1/4 cup per egg in sweet bakes."), ("plain yogurt", "1/4 cup per egg in cakes and muffins.")],
    "cheese": [("nutritional yeast", "Gives a cheesy taste to sauces and toppings.")],
    "parmesan cheese": [("pecorino", "Same amount; a little saltier."), ("aged cheddar", "Grate finely."), ("nutritional yeast", "A dairy-free cheesy topping.")],
    "mozzarella cheese": [("provolone", "Melts the same way."), ("cheddar", "Melts well; stronger taste.")],
    "cheddar cheese": [("gouda", "Melts well."), ("monterey jack", "Milder; melts smoothly.")],
    "feta cheese": [("goat cheese", "Crumbles the same way."), ("halloumi", "Firmer and less salty.")],
    "ricotta cheese": [("cottage cheese", "Blend it smooth first."), ("cream cheese", "Richer; thin with milk.")],
    "mascarpone cheese": [("cream cheese", "Beat with a spoon of cream."), ("ricotta", "Blend it smooth.")],
    "cream cheese": [("mascarpone", "Same amount."), ("ricotta", "Blend it smooth.")],
    "condensed milk": [("evaporated milk and sugar", "1 cup evaporated milk simmered with 1 1/4 cups sugar.")],
    "evaporated milk": [("milk", "Simmer it until reduced by half."), ("cream", "Use a little less.")],
    "coconut milk": [("cream", "Same amount."), ("evaporated milk", "Same amount."), ("plain yogurt", "Stir in off the heat.")],
    # Baking
    "flour": [("whole wheat flour", "Same amount; denser."), ("oat", "Blend into flour; for pancakes and crumbles."), ("almond flour", "In cakes and pancakes; use a little more.")],
    "cornstarch": [("flour", "Twice as much to thicken."), ("arrowroot", "Same amount.")],
    "cornflour": [("flour", "Twice as much to thicken."), ("arrowroot", "Same amount.")],
    "baking powder": [("baking soda and lemon juice", "1/4 tsp soda with 1/2 tsp lemon juice per tsp.")],
    "baking soda": [("baking powder", "Three times as much.")],
    "yeast": [("baking powder", "For quick breads; the texture is more like soda bread.")],
    "sugar": [("honey", "3/4 as much, and a little less liquid."), ("maple syrup", "3/4 as much, and a little less liquid.")],
    "brown sugar": [("sugar and honey", "1 cup sugar with 1 tbsp honey."), ("coconut sugar", "Same amount.")],
    "honey": [("maple syrup", "Same amount."), ("sugar", "1 1/4 as much, plus a splash of water.")],
    "maple syrup": [("honey", "Same amount."), ("brown sugar", "Dissolved in a little water.")],
    "vanilla": [("maple syrup", "The same amount adds a similar warmth."), ("cinnamon", "A pinch, for a different warmth.")],
    "chocolate": [("cocoa powder and butter", "3 tbsp cocoa with 1 tbsp butter per 30 g."), ("chocolate chips", "Same amount.")],
    "cocoa": [("chocolate", "Melted; reduce the fat and sugar a little.")],
    "gelatin": [("agar agar", "Use half as much and boil it briefly.")],
    # Sour, savoury and sauces
    "lemon": [("lime", "Same amount."), ("white wine vinegar", "Half as much, for sharpness.")],
    "lime": [("lemon", "Same amount."), ("rice vinegar", "Half as much, for sharpness.")],
    "vinegar": [("lemon juice", "Same amount."), ("lime juice", "Same amount.")],
    "wine": [("stock and a splash of vinegar", "Same amount of stock with 1 tsp vinegar per cup."), ("grape juice", "In sweet dishes.")],
    "stock": [("water and a stock cube", "Same amount."), ("water and soy sauce", "1 tbsp soy sauce per 2 cups water.")],
    "broth": [("water and a stock cube", "Same amount."), ("water and soy sauce", "1 tbsp soy sauce per 2 cups water.")],
    "soy sauce": [("tamari", "Same amount; gluten-free."), ("fish sauce", "Half as much.")],
    "fish sauce": [("soy sauce", "Same amount, with a squeeze of lime.")],
    "tomato paste": [("ketchup", "Same amount; a little sweeter."), ("tomato", "Blend and cook down until thick.")],
    "tomato sauce": [("tomato", "Chopped or canned, simmered down."), ("tomato paste", "Thinned with water.")],
    "mayonnaise": [("plain yogurt", "Same amount."), ("sour cream", "Same amount.")],
    "ketchup": [("tomato paste", "With a little sugar and vinegar.")],
    "mustard": [("horseradish", "Use less."), ("mustard powder", "1 tsp powder with 1 tbsp water.")],
    "worcestershire sauce": [("soy sauce", "Same amount, with a pinch of sugar.")],
    "peanut butter": [("almond butter", "Same amount."), ("sunflower seed butter", "Same amount; nut-free.")],
    # Aromatics, herbs and spices
    "onion": [("shallot", "Milder; use a little more."), ("leek", "Milder and sweeter."), ("springonion", "Add it near the end.")],
    "shallot": [("onion", "Use about half as much."), ("springonion", "The white parts.")],
    "springonion": [("chive", "Same amount."), ("onion", "A little, finely chopped.")],
    "garlic": [("garlic powder", "1/8 tsp per clove."), ("shallot", "A different but gentle flavour.")],
    "ginger": [("ground ginger", "1/4 tsp per tbsp of fresh."), ("galangal", "Same amount; more citrusy.")],
    "basil": [("parsley", "Add a little mint for the sweetness."), ("spinach", "In pesto, for colour and body.")],
    "parsley": [("cilantro", "Stronger taste."), ("chive", "Same amount.")],
    "cilantro": [("parsley", "With a squeeze of lime."), ("mint", "Use less.")],
    "thyme": [("oregano", "Same amount."), ("rosemary", "Use half as much.")],
    "rosemary": [("thyme", "Twice as much.")],
    "oregano": [("thyme", "Same amount."), ("basil", "Same amount.")],
    "mint": [("basil", "Same amount.")],
    "cumin": [("ground coriander", "Same amount."), ("chili powder", "Half as much; adds heat.")],
    "paprika": [("chili powder", "Half as much; hotter."), ("cayenne", "A pinch only.")],
    "cinnamon": [("nutmeg", "Use a quarter as much."), ("allspice", "Use half as much.")],
    "chili": [("chili flake", "1/2 tsp per chili."), ("hot sauce", "A few drops at a time.")],
    # Proteins
    "chicken": [("turkey", "Same amount and cooking."), ("tofu", "Press it and fry until golden."), ("chickpea", "For a vegetarian version.")],
    "beef": [("lamb", "Same amount."), ("pork", "Same amount."), ("mushroom", "For a vegetarian version.")],
    "pork": [("chicken", "Cook until no longer pink."), ("turkey", "Same amount.")],
    "lamb": [("beef", "Same amount.")],
    "bacon": [("ham", "Same amount."), ("pancetta", "Same amount."), ("paprika", "Smoked, for the smoky taste in vegetarian cooking.")],
    "sausage": [("bacon", "Chopped."), ("chorizo", "Spicier.")],
    "salmon": [("trout", "Same cooking."), ("cod", "Milder and flakier.")],
    "fish": [("cod", "Any firm white fish."), ("tofu", "Firm tofu for a vegetarian version.")],
    "shrimp": [("chicken", "Small pieces."), ("fish", "Firm white fish in chunks.")],
    "tofu": [("tempeh", "Same amount."), ("chickpea", "For stir-fries and curries."), ("paneer", "Not vegan.")],
    # Grains and starches
    "rice": [("quinoa", "Same cooking method."), ("couscous", "Ready in 5 minutes."), ("cauliflower rice", "A lighter option.")],
    "pasta": [("rice noodle", "Soak or boil briefly."), ("zucchini noodle", "A lighter option.")],
    "spaghetti": [("linguine", "Same cooking."), ("rice noodle", "Soak or boil briefly.")],
    "noodle": [("spaghetti", "Same amount."), ("rice", "Serve alongside instead.")],
    "bread": [("tortilla", "For wraps and toasties."), ("pita", "Same use.")],
    "breadcrumb": [("oat", "Blitzed."), ("cracker", "Crushed.")],
    "tortilla": [("pita", "Same use."), ("lettuce", "Large leaves as wraps.")],
    "couscous": [("quinoa", "Same amount."), ("rice", "Same amount.")],
    "oat": [("flour", "In baking."), ("quinoa", "Flakes, the same way.")],
    # Vegetables
    "potato": [("sweet potato", "Same cooking; sweeter."), ("cauliflower", "A lighter mash.")],
    "carrot": [("parsnip", "Same cooking."), ("sweet potato", "Same cooking.")],
    "spinach": [("kale", "Cook a little longer."), ("chard", "Same way.")],
    "kale": [("spinach", "Cooks faster."), ("cabbage", "Shredded.")],
    "lettuce": [("spinach", "Young leaves."), ("cabbage", "Finely shredded.")],
    "mushroom": [("eggplant", "Cubed and browned."), ("zucchini", "Same cooking.")],
    "zucchini": [("eggplant", "Same cooking."), ("cucumber", "Only raw, in salads.")],
    "eggplant": [("zucchini", "Same cooking."), ("mushroom", "Same cooking.")],
    "bellpepper": [("zucchini", "For bulk and colour."), ("carrot", "For crunch and sweetness.")],
    "tomato": [("canned tomato", "Same amount."), ("bellpepper", "Red, for colour and sweetness.")],
    "celery": [("fennel", "Same crunch."), ("carrot", "For crunch.")],
    "cucumber": [("zucchini", "Raw and thinly sliced."), ("celery", "For crunch.")],
    "avocado": [("hummus", "As a spread."), ("cream cheese", "As a spread.")],
    "bean": [("chickpea", "Same amount."), ("lentil", "Cooked.")],
    "chickpea": [("bean", "White beans, same amount."), ("lentil", "Cooked.")],
    "lentil": [("split pea", "Same cooking."), ("bean", "Canned.")],
    # Fruit and nuts
    "berry": [("frozen berry", "Same amount, thawed.")],
    "strawberry": [("raspberry", "Same amount."), ("frozen berry", "Same amount, thawed.")],
    "raspberry": [("strawberry", "Same amount."), ("blackberry", "Same amount.")],
    "blueberry": [("blackberry", "Same amount."), ("raspberry", "Same amount.")],
    "blackberry": [("blueberry", "Same amount."), ("raspberry", "Same amount.")],
    "banana": [("apple sauce", "In baking."), ("mango", "In smoothies.")],
    "apple": [("pear", "Same amount.")],
    "pear": [("apple", "Same amount.")],
    "orange": [("mandarin", "Same amount."), ("lemon", "Use less; sharper.")],
    "peach": [("nectarine", "Same amount."), ("mango", "Same amount.")],
    "almond": [("cashew", "Same amount."), ("sunflower seed", "Nut-free.")],
    "walnut": [("pecan", "Same amount."), ("almond", "Same amount.")],
    "nut": [("sunflower seed", "Nut-free."), ("pumpkin seed", "Nut-free.")],
}


# Products that still act like the food they come from (lemon juice is lemon); chicken
# stock or tomato paste do not, so they never fall back to the plain food's swaps.
ACTS_LIKE_THE_FOOD = {"juice", "zest", "extract", "essence", "powder", "flake"}

# Cheeses swap well only within their kind: feta is no stand-in for parmesan.
CHEESE_KINDS = [
    {"parmesan", "pecorino", "grana", "cheddar", "gouda", "gruyere", "emmental", "manchego", "comte", "asiago"},
    {"mozzarella", "provolone", "monterey", "jack", "fontina", "cheddar", "gouda", "emmental"},
    {"ricotta", "mascarpone", "cottage", "cream", "quark"},
    {"feta", "halloumi", "goat", "paneer"},
    {"brie", "camembert"},
    {"stilton", "gorgonzola", "roquefort", "blue"},
]


def swap_keys(ingredient: str) -> list[str]:
    """Table keys for an ingredient, most specific first ("parmesan cheese", then "cheese")."""
    food = analyse(ingredient)
    if not food.head:
        return []
    named = " ".join(food.words)
    if food.derived:
        keys = [f"{named} {food.derived}", food.derived]
        if food.derived not in ACTS_LIKE_THE_FOOD:
            return keys
    else:
        keys = []
    keys.append(named)
    keys += [f"{identity} {food.head}" for identity in sorted(food.identity)]
    keys += [f"{variety} {food.head}" for variety in sorted(food.varieties)]
    keys.append(food.head)
    return list(dict.fromkeys(key for key in keys if key))


def table_swaps(ingredient: str) -> list[tuple[str, str]]:
    for key in swap_keys(ingredient):
        if key in KITCHEN_SWAPS:
            return KITCHEN_SWAPS[key]
    return []


def _same_food(first: str, second: str) -> bool:
    """The same food named differently ("eggs", "egg"); "flax egg" is a different one."""
    a, b = analyse(first), analyse(second)
    return a.words == b.words and a.derived == b.derived


def _same_kind(food, other) -> bool:
    if food.head != other.head or food.derived != other.derived:
        return False
    if food.head == "cheese":
        return any(set(food.words) & kind and set(other.words) & kind for kind in CHEESE_KINDS)
    # Red onion for shallot-sized jobs, whole milk for skim; not ice cream for cream.
    return food.identity == other.identity


def pantry_lookalikes(ingredient: str, pantry_names: list[str]) -> list[str]:
    """Pantry foods of the same kind that do not count as the ingredient itself."""
    food = analyse(ingredient)
    return [
        name for name in pantry_names
        if _same_kind(food, analyse(name, "pantry")) and not pantry_match(ingredient, name)
    ]


def pantry_name_for(suggestion: str, pantry_names: list[str], ingredient: str) -> str | None:
    """The pantry entry a single-food suggestion names ("lime" -> "limes"). A mix
    ("milk and lemon juice") is a method, not one food, so it is never marked as owned,
    and a pantry entry that is the ingredient itself (plain "cheese" for cheddar) is no swap."""
    if " and " in suggestion:
        return None
    return next((name for name in pantry_names if pantry_match(suggestion, name) and not pantry_match(ingredient, name)), None)


def swaps_for(
    ingredient: str,
    pantry_names: list[str],
    is_safe,
    model_suggestions: list[dict] | None = None,
    limit: int = 3,
) -> list[dict]:
    """Merge pantry, table and model swaps for one ingredient: safe, distinct, pantry first."""
    # (from the model?, suggestion): known swaps come before the model's, pantry foods first within each.
    candidates: list[tuple[bool, dict]] = []
    for name in pantry_lookalikes(ingredient, pantry_names):
        candidates.append((False, {"name": name, "reason": f"Another {analyse(ingredient).head} you already have.", "in_pantry": True}))
    for name, reason in table_swaps(ingredient):
        owned = pantry_name_for(name, pantry_names, ingredient)
        candidates.append((False, {"name": owned or name, "reason": reason, "in_pantry": owned is not None}))
    for suggestion in model_suggestions or []:
        name = str(suggestion.get("name", "")).strip().lower()
        if not name:
            continue
        owned = pantry_name_for(name, pantry_names, ingredient)
        reason = str(suggestion.get("reason") or "A practical substitute; check that it suits the recipe.")
        candidates.append((True, {"name": owned or name, "reason": reason, "in_pantry": owned is not None}))
    candidates.sort(key=lambda entry: (entry[0], not entry[1]["in_pantry"]))

    chosen: list[dict] = []
    for _, candidate in candidates:
        name = candidate["name"]
        if _same_food(ingredient, name) or not is_safe(name):
            continue  # the ingredient itself ("fresh basil" for basil), or unsafe for this cook
        if any(pantry_match(name, other["name"]) or name == other["name"] for other in chosen):
            continue
        chosen.append(candidate)
    return chosen[:limit]
