"""User-testing fixes: AI recipes that make sense, diet fallbacks, use-soon ranking, pantry updates and swaps."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

_database_file = None
if "MEALMATCH_DATABASE_URL" not in os.environ:
    _database_file = tempfile.NamedTemporaryFile(prefix="mealmatch-recipes-test-", suffix=".db", delete=False)
    _database_file.close()
    os.environ["MEALMATCH_DATABASE_URL"] = f"sqlite:///{_database_file.name}"

from database import Base, SessionLocal, engine  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
from models import PantryItem, Recipe, User, UserPreference  # noqa: E402
from pantry_usage import amount_in_pantry_unit, remaining_amount  # noqa: E402
from recipe_relevance import (  # noqa: E402
    choose_pantry_for_request,
    dessert_ingredients_for_savoury,
    is_sweet_request,
    lacks_sweetness,
    request_flavour,
    request_terms,
    savoury_ingredients_for_dessert,
    title_foods_missing,
    wants_pantry_only,
)
from substitutions import swaps_for  # noqa: E402
from recommender import calculate_personalized_score, dietary_conflict, recommendation_sort_key  # noqa: E402

USER = 7


def day(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def pantry(*entries):
    return [SimpleNamespace(ingredient=name, category=category, expiry_date=expiry, quantity="1 piece") for name, category, expiry in entries]


def recipe(title, ingredients, cuisine="British", cooking_time=20):
    return SimpleNamespace(title=title, ingredients=",".join(ingredients), cuisine=cuisine, cooking_time=cooking_time)


class DessertRelevanceTests(unittest.TestCase):
    references = [
        recipe("Creamy Tomato Soup", ["tomato", "onion", "double cream", "garlic", "vegetable stock"]),
        recipe("Potato Gratin", ["potato", "double cream", "garlic", "cheddar cheese"]),
        recipe("Apple & Blackberry Crumble", ["plain flour", "caster sugar", "butter", "apples", "blackberries", "ice cream"]),
        recipe("Banana Pancakes", ["banana", "eggs", "vanilla extract", "raspberries"]),
    ]
    items = pantry(
        ("ice cream", "frozen", day(60)), ("onion", "vegetables", day(2)), ("tomatoes", "vegetables", day(2)),
        ("potatoes", "vegetables", day(3)), ("blackberries", "fruit", day(2)), ("banana", "fruit", day(1)),
        ("garlic butter", "dairy", day(4)),
    )

    def test_ice_cream_is_one_food_and_a_dessert(self):
        self.assertEqual(request_terms("ice cream"), ["ice cream"])
        self.assertTrue(is_sweet_request("ice cream"))
        self.assertTrue(is_sweet_request("chocolate brownies"))
        self.assertTrue(is_sweet_request("apple pie"))
        self.assertFalse(is_sweet_request("chicken pie"))

    def test_a_dessert_is_never_offered_savoury_pantry_food(self):
        offered, _ = choose_pantry_for_request("ice cream", self.items, self.references)
        self.assertIn("ice cream", offered)
        self.assertIn("blackberries", offered)
        for savoury in ("onion", "tomatoes", "potatoes", "garlic butter"):
            self.assertNotIn(savoury, offered)

    def test_savoury_ingredients_in_a_dessert_are_caught_unless_asked_for(self):
        tomato_pie = ["graham cracker crumbs", "sugar", "onion", "grape tomato", "ice cream"]
        self.assertEqual(savoury_ingredients_for_dessert("ice cream", tomato_pie), ["onion", "grape tomato"])
        self.assertEqual(savoury_ingredients_for_dessert("chocolate brownie", ["cocoa", "crushed red pepper flakes"]), ["crushed red pepper flakes"])
        self.assertEqual(savoury_ingredients_for_dessert("carrot cake", ["carrot", "flour", "sugar"]), [])
        self.assertEqual(savoury_ingredients_for_dessert("tomato pasta", ["tomato", "onion"]), [])


class TasteRequestTests(unittest.TestCase):
    """Design iteration 3: "a sweet dish with what I have" produced beef fritters."""

    references = [
        recipe("Beef Stew", ["beef", "onion", "carrot", "potato", "beef stock"]),
        recipe("Berry Fool", ["raspberries", "double cream", "caster sugar"]),
        recipe("Custard Tart", ["eggs", "milk", "sugar", "plain flour", "butter"]),
    ]
    items = pantry(
        ("sliced beef sirloin", "meat", day(0)), ("red onion", "vegetables", day(0)), ("carrot", "vegetables", day(1)),
        ("blueberries", "fruit", day(1)), ("blueberry", "fruit", day(5)), ("banana", "fruit", day(2)),
        ("eggs", "eggs", day(10)), ("milk", "dairy", day(4)), ("honey", "pantry", day(200)),
        ("raspberries", "fruit", day(-1)),
    )

    def test_a_taste_word_sets_the_flavour_unless_it_names_a_food(self):
        self.assertEqual(request_flavour("sweet dish with what I have in my pantry"), "sweet")
        self.assertEqual(request_flavour("something sweet"), "sweet")
        self.assertEqual(request_flavour("a savoury snack"), "savoury")
        for savoury in ("sweet and sour chicken", "sweet potato curry", "sweet chilli salmon", "sweet corn soup", "quick dinner"):
            self.assertIsNone(request_flavour(savoury), savoury)

    def test_something_sweet_is_built_on_the_sweet_food_that_needs_using(self):
        offered, scores = choose_pantry_for_request("a sweet dish with what I have in my pantry", self.items, self.references)
        self.assertEqual(offered[:2], ["blueberries", "banana"])  # most urgent sweet food first, one entry per food
        self.assertNotIn("blueberry", offered)
        self.assertNotIn("raspberries", offered)  # expired
        for savoury in ("sliced beef sirloin", "red onion", "carrot"):
            self.assertNotIn(savoury, offered)
            self.assertEqual(scores[savoury], 0)
        self.assertIn("eggs", offered)  # a dessert basic from the sweet reference dishes

    def test_finished_recipes_must_match_the_taste(self):
        request = "sweet dish with what I have in my pantry"
        self.assertEqual(savoury_ingredients_for_dessert(request, ["beef", "carrot", "flour", "sugar"]), ["beef", "carrot"])
        self.assertTrue(lacks_sweetness(request, ["flour", "egg", "milk", "butter"]))
        self.assertFalse(lacks_sweetness(request, ["flour", "egg", "blueberries"]))
        self.assertFalse(lacks_sweetness("chicken curry", ["chicken", "onion"]))
        self.assertEqual(dessert_ingredients_for_savoury("a savoury snack", ["cheddar", "chocolate syrup", "ice cream"]), ["chocolate syrup", "ice cream"])
        pantry_names = ["banana", "dates", "whipped cream", "potato"]
        self.assertEqual(title_foods_missing("Banana Date Bites", ["flour", "sugar", "blueberries"], pantry_names), ["banana", "date"])
        self.assertEqual(title_foods_missing("Ice Cream Sundae", ["ice cream", "chocolate syrup"], pantry_names), [])
        self.assertEqual(title_foods_missing("Sweet Potato Pie", ["sweet potato", "sugar"], pantry_names), [])
        self.assertTrue(wants_pantry_only(request))
        self.assertTrue(wants_pantry_only("use up my leftovers"))
        self.assertFalse(wants_pantry_only("a quick chicken dinner"))


class SwapTests(unittest.TestCase):
    safe = staticmethod(lambda name: True)

    def names(self, ingredient, pantry_names, **options):
        return [(item["name"], item["in_pantry"]) for item in swaps_for(ingredient, pantry_names, options.pop("is_safe", self.safe), **options)]

    def test_pantry_foods_of_the_same_kind_come_first(self):
        self.assertEqual(self.names("raspberries", ["blackberries", "strawberry"])[:2], [("strawberry", True), ("blackberries", True)])
        self.assertIn(("feta cheese", True), self.names("halloumi", ["feta cheese"]))
        self.assertNotIn(("brie cheese", True), self.names("parmesan", ["brie cheese"]))  # a different kind of cheese
        self.assertNotIn("ice cream", [name for name, _ in self.names("double cream", ["ice cream"])])

    def test_products_are_not_swapped_like_the_food_they_come_from(self):
        stock = [name for name, _ in self.names("chicken stock", [])]
        self.assertNotIn("turkey", stock)
        self.assertIn("water and a stock cube", stock)
        self.assertEqual(self.names("lemon juice", ["limes"])[0], ("limes", True))

    def test_a_mix_is_never_marked_as_owned_and_unsafe_swaps_are_dropped(self):
        self.assertIn(("milk and lemon juice", False), self.names("buttermilk", ["lemon", "milk"]))
        swaps = self.names("milk", [], is_safe=lambda name: "soy" not in name)
        self.assertNotIn("soy milk", [name for name, _ in swaps])
        self.assertIn(("oat milk", False), swaps)

    def test_model_swaps_fill_in_after_known_ones(self):
        swaps = self.names("garlic powder", ["lemon"], model_suggestions=[{"name": "lemon", "reason": "x"}, {"name": "dried oregano", "reason": "y"}])
        self.assertEqual(swaps[0], ("shallot", False))
        self.assertIn(("lemon", True), swaps)


class DietAndRankingTests(unittest.TestCase):
    def test_look_alike_names_do_not_break_diets(self):
        self.assertIsNone(dietary_conflict(["peanut butter", "coconut milk", "butternut squash"], ["dairy-free", "vegan"]))
        self.assertIsNone(dietary_conflict(["buckwheat flour", "rice noodles"], ["gluten-free"]))
        self.assertEqual(dietary_conflict(["spaghetti"], ["gluten-free"]), "gluten-free preference")
        self.assertEqual(dietary_conflict(["chorizo"], ["vegetarian"]), "vegetarian preference")
        self.assertEqual(dietary_conflict(["parmesan"], ["vegan"]), "vegan preference")

    def score(self, item, pantry_items, dietary=(), allergies=()):
        return calculate_personalized_score(item, pantry_items, {}, list(dietary), list(allergies), [])

    def test_food_due_soon_ranks_first_and_expired_food_does_not_count(self):
        items = pantry(("spinach", "vegetables", day(1)), ("rice", "grains", day(90)), ("egg", "eggs", day(30)), ("milk", "dairy", day(-2)))
        rescue = self.score(recipe("Spinach Omelette", ["spinach", "egg", "cheese", "butter"]), items)
        full_match = self.score(recipe("Egg Fried Rice", ["rice", "egg"]), items)
        self.assertEqual(rescue["expiring_matched_ingredients"], ["spinach"])
        self.assertEqual(rescue["use_soon_used"], [{"ingredient": "spinach", "days_left": 1}])
        self.assertGreater(recommendation_sort_key(rescue), recommendation_sort_key(full_match))
        expired = self.score(recipe("Milk Pudding", ["milk", "sugar"]), items)
        self.assertEqual(expired["matched_ingredients"], [])

    def test_diet_conflicts_sort_last_and_allergies_score_zero(self):
        items = pantry(("chicken", "meat", day(1)), ("rice", "grains", day(90)), ("peanut", "pantry", day(1)))
        chicken = self.score(recipe("Chicken Rice", ["chicken", "rice"]), items, dietary=["vegetarian"])
        plain = self.score(recipe("Plain Rice", ["rice", "salt"]), items, dietary=["vegetarian"])
        self.assertFalse(chicken["eligible"])
        self.assertGreater(chicken["final_score"], 0)
        self.assertEqual(chicken["diet_conflicts"], [{"diet": "vegetarian", "ingredients": ["chicken"]}])
        self.assertGreater(recommendation_sort_key(plain), recommendation_sort_key(chicken))
        satay = self.score(recipe("Peanut Rice", ["peanut", "rice"]), items, allergies=["peanuts"])
        self.assertEqual(satay["final_score"], 0)


class PantryUsageTests(unittest.TestCase):
    def test_units_are_converted_to_the_pantry_unit(self):
        self.assertAlmostEqual(amount_in_pantry_unit("milk", 1, "cup", "bottle"), .24)
        self.assertAlmostEqual(amount_in_pantry_unit("eggs", 2, "pieces", "cartons"), 2 / 12)
        self.assertAlmostEqual(amount_in_pantry_unit("garlic", 2, "cloves", "pieces"), .2)
        self.assertAlmostEqual(amount_in_pantry_unit("spinach", 2, "cups", "g"), 57.6)
        self.assertEqual(amount_in_pantry_unit("red onion", 1, "small finely diced", "pieces"), 1)
        self.assertIsNone(amount_in_pantry_unit("rice", 1, "cup", "sacks of luck"))

    def test_remaining_amounts_are_rounded_for_display(self):
        self.assertEqual(remaining_amount(1, .24, "bottle"), .8)
        self.assertEqual(remaining_amount(500, 57.6, "g"), 442)
        self.assertEqual(remaining_amount(1, .97, "box"), 0)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Another test module may have deleted the shared database file: reconnect and recreate it.
        engine.dispose()
        Base.metadata.create_all(bind=engine)
        database = SessionLocal()
        if not database.get(User, USER):
            database.add(User(id=USER, name="Recipe test user"))
        database.commit()
        database.close()
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        if _database_file is not None:
            engine.dispose()
            Path(_database_file.name).unlink(missing_ok=True)

    def setUp(self):
        database = SessionLocal()
        database.query(PantryItem).filter(PantryItem.user_id == USER).delete()
        database.query(UserPreference).filter(UserPreference.user_id == USER).delete()
        database.commit()
        database.close()

    def add(self, *objects):
        database = SessionLocal()
        database.add_all(objects)
        database.commit()
        ids = [getattr(item, "id", None) for item in objects]
        database.close()
        return ids

    def pantry_quantities(self):
        return {item["ingredient"]: item["quantity"] for item in self.client.get(f"/pantry/{USER}").json()}

    def test_pantry_changes_when_the_meal_is_ready(self):
        [recipe_id] = self.add(Recipe(
            title="Test Omelette", ingredients="egg,milk,garlic", instructions="Whisk.\n\nCook.",
            ingredient_details=json.dumps([
                {"name": "egg", "amount": 2, "unit": "pieces"},
                {"name": "milk", "amount": 1, "unit": "cup"},
                {"name": "garlic", "amount": 2, "unit": "cloves"},
            ]),
            cooking_time=5, prep_time=5, source="MealMatch",
        ))
        self.add(
            PantryItem(user_id=USER, ingredient="eggs", quantity="3 pieces", expiry_date=day(2), category="eggs"),
            PantryItem(user_id=USER, ingredient="milk", quantity="1 bottle", expiry_date=day(4), category="dairy"),
            PantryItem(user_id=USER, ingredient="garlic", quantity="1 piece", expiry_date=day(20), category="vegetables"),
        )
        started = self.client.post(f"/recipes/{recipe_id}/cook/{USER}", json={"servings": 1})
        self.assertEqual(started.status_code, 200, started.text)
        self.assertEqual(self.pantry_quantities()["milk"], "1 bottle")  # nothing changes while cooking

        done = self.client.post(f"/cooking-session/{USER}/complete")
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(self.pantry_quantities(), {"eggs": "1 piece", "milk": "0.8 bottle", "garlic": "0.8 piece"})
        self.assertEqual(done.json()["rescued_items"], ["eggs", "milk"])

    def test_cancelling_leaves_the_pantry_alone(self):
        [recipe_id] = self.add(Recipe(title="Test Toast", ingredients="bread", instructions="Toast.\n\nServe.", cooking_time=3, source="MealMatch"))
        self.add(PantryItem(user_id=USER, ingredient="bread", quantity="2 pieces", expiry_date=day(3), category="bakery"))
        self.client.post(f"/recipes/{recipe_id}/cook/{USER}", json={"servings": 1})
        cancelled = self.client.post(f"/cooking-session/{USER}/cancel")
        self.assertEqual(cancelled.json()["message"], "Cooking cancelled. Your pantry is unchanged.")
        self.assertEqual(self.pantry_quantities(), {"bread": "2 pieces"})

    def test_recipes_that_break_a_diet_come_last_and_allergies_are_hidden(self):
        self.add(
            Recipe(title="Zz Test Beef Stew", ingredients="beef,onion", instructions="a\n\nb", cooking_time=60, source="TheMealDB", image_url="https://example.com/a.jpg"),
            Recipe(title="Zz Test Peanut Noodles", ingredients="peanut butter,noodles", instructions="a\n\nb", cooking_time=10, source="TheMealDB", image_url="https://example.com/b.jpg"),
            Recipe(title="Zz Test Lentil Soup", ingredients="lentil,onion", instructions="a\n\nb", cooking_time=30, source="TheMealDB", image_url="https://example.com/c.jpg"),
            UserPreference(user_id=USER, dietary_restrictions="vegetarian", allergies="peanuts", onboarding_complete=True),
        )
        titles = [item["title"] for item in self.client.get("/recipes", params={"user_id": USER}).json()]
        self.assertNotIn("Zz Test Peanut Noodles", titles)
        self.assertLess(titles.index("Zz Test Lentil Soup"), titles.index("Zz Test Beef Stew"))
        stew = next(item for item in self.client.get("/recipes", params={"user_id": USER}).json() if item["title"] == "Zz Test Beef Stew")
        self.assertEqual(stew["diet_conflicts"], [{"diet": "vegetarian", "ingredients": ["beef"]}])

    def test_web_photos_are_downloaded_once_and_served_by_the_server(self):
        stew, offline, plain = self.add(
            Recipe(title="Zz Photo Stew", ingredients="beef", instructions="a\n\nb", cooking_time=5, source="TheMealDB", image_url="https://example.com/stew.jpg"),
            Recipe(title="Zz Offline Photo", ingredients="rice", instructions="a\n\nb", cooking_time=5, source="TheMealDB", image_url="https://example.com/gone.jpg"),
            Recipe(title="Zz No Photo", ingredients="rice", instructions="a\n\nb", cooking_time=5, source="MealMatch"),
        )
        photo = SimpleNamespace(content=b"jpeg-bytes", headers={"content-type": "image/jpeg"}, raise_for_status=lambda: None)

        def download(url, **_):
            if url.endswith("gone.jpg"):
                raise requests.ConnectionError()
            return photo

        with tempfile.TemporaryDirectory() as cache, patch("routers.recipes.PHOTO_CACHE", Path(cache)), patch("routers.recipes.requests.get", side_effect=download) as get:
            first = self.client.get(f"/recipes/{stew}/photo")
            again = self.client.get(f"/recipes/{stew}/photo")
            self.assertEqual((first.status_code, first.content, first.headers["content-type"]), (200, b"jpeg-bytes", "image/jpeg"))
            self.assertEqual(again.content, b"jpeg-bytes")
            self.assertEqual([call.args[0] for call in get.call_args_list].count("https://example.com/stew.jpg"), 1)
            # A photo that cannot be fetched fails, so the card draws its foods instead.
            self.assertEqual(self.client.get(f"/recipes/{offline}/photo").status_code, 502)
            self.assertEqual(self.client.get(f"/recipes/{plain}/photo").status_code, 404)

    def generated(self, title, ingredients):
        return {
            "title": title, "cuisine": "Dessert", "prep_time": 5, "cooking_time": 5, "servings": 2, "calories": 300,
            "ingredients": [{"name": name, "amount": 1, "unit": "cup"} for name in ingredients],
            "steps": [{"instruction": f"Step {number}.", "minutes": 2} for number in range(1, 5)],
        }

    def test_ai_desserts_with_savoury_food_and_repeated_ideas_are_retried(self):
        self.add(PantryItem(user_id=USER, ingredient="ice cream", quantity="1 tub", expiry_date=day(60), category="frozen"))
        answers = iter([
            self.generated("Creamy Tomato Ice Cream Pie", ["ice cream", "tomato", "onion", "sugar", "biscuit"]),
            self.generated("Zz Vanilla Sundae", ["ice cream", "chocolate syrup", "banana", "cherry", "wafer"]),
        ])
        with patch("routers.recipes.generate_recipe_from_pantry", side_effect=lambda *_: next(answers)):
            first = self.client.post(f"/ai-recipes/{USER}", json={"request": "ice cream"})
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["title"], "Zz Vanilla Sundae")
        self.assertEqual(first.json()["generation_attempts"], 2)

        answers = iter([
            self.generated("Zz Vanilla Sundaes", ["ice cream", "chocolate syrup", "banana", "cherry", "wafer"]),
            self.generated("Zz Affogato", ["ice cream", "espresso", "cocoa", "biscotti", "sugar"]),
        ])
        with patch("routers.recipes.generate_recipe_from_pantry", side_effect=lambda *_: next(answers)):
            second = self.client.post(f"/ai-recipes/{USER}", json={"request": "ice cream", "avoid_titles": ["Zz Vanilla Sundae"]})
        self.assertEqual(second.json()["title"], "Zz Affogato")

        # The same dish asked for again later reuses the saved recipe instead of adding a twin.
        answers = iter([self.generated("Zz Vanilla Sundae", ["ice cream", "chocolate syrup", "banana", "cherry", "wafer"])])
        with patch("routers.recipes.generate_recipe_from_pantry", side_effect=lambda *_: next(answers)):
            third = self.client.post(f"/ai-recipes/{USER}", json={"request": "ice cream"})
        self.assertEqual(third.json()["id"], first.json()["id"])
        database = SessionLocal()
        self.assertEqual(database.query(Recipe).filter(Recipe.title == "Zz Vanilla Sundae").count(), 1)
        database.close()
        self.assertEqual(first.json()["image_url"], "")
        self.assertNotIn("image_pending", first.json())

        # An AI recipe that has a photo is still one card, not two.
        database = SessionLocal()
        database.get(Recipe, first.json()["id"]).image_url = "/recipe-images/sundae.webp"
        database.add(Recipe(title="Zz Photo Recipe", ingredients="rice", instructions="a\n\nb", cooking_time=5, source="TheMealDB", image_url="https://example.com/r.jpg"))
        database.commit()
        database.close()
        listed = self.client.get("/recipes", params={"user_id": USER}).json()
        self.assertEqual([item["id"] for item in listed].count(first.json()["id"]), 1)
        # Photos are no longer made or shown for AI recipes: the client draws their foods.
        self.assertEqual(next(item for item in listed if item["id"] == first.json()["id"])["image_url"], "")
        self.assertEqual(self.client.post(f"/recipes/{first.json()['id']}/image").status_code, 404)

    def test_a_sweet_request_keeps_only_sweet_recipes(self):
        self.add(
            PantryItem(user_id=USER, ingredient="beef sirloin", quantity="1 piece", expiry_date=day(0), category="meat"),
            PantryItem(user_id=USER, ingredient="blueberries", quantity="1 box", expiry_date=day(1), category="fruit"),
            PantryItem(user_id=USER, ingredient="yogurt", quantity="1 tub", expiry_date=day(5), category="dairy"),
        )
        answers = iter([
            self.generated("Zz Sweet Beef Fritters", ["beef sirloin", "carrot", "flour", "egg", "sugar"]),
            self.generated("Zz Plain Pancakes", ["flour", "egg", "milk", "butter", "salt"]),
            self.generated("Zz Blueberry Parfait", ["yogurt", "blueberries", "honey", "oats", "mint"]),
        ])
        prompts = []

        def answer(offered, prompt):
            prompts.append((offered, prompt))
            return next(answers)

        with patch("routers.recipes.generate_recipe_from_pantry", side_effect=answer):
            made = self.client.post(f"/ai-recipes/{USER}", json={"request": "sweet dish with what I have in my pantry"})
        self.assertEqual(made.status_code, 200, made.text)
        self.assertEqual(made.json()["title"], "Zz Blueberry Parfait")
        self.assertEqual(made.json()["generation_attempts"], 3)
        offered, prompt = prompts[0]
        self.assertNotIn("beef sirloin", offered)
        self.assertIn("blueberries", offered)
        self.assertIn("It must be a sweet dish", prompt)
        self.assertIn("Build it from the pantry foods listed", prompt)
        self.assertIn("not sweet", prompts[2][1])

    def test_a_vegan_is_offered_only_food_they_can_eat(self):
        self.add(
            PantryItem(user_id=USER, ingredient="cheese", quantity="1 block", expiry_date=day(1), category="dairy"),
            PantryItem(user_id=USER, ingredient="eggs", quantity="6 pieces", expiry_date=day(2), category="eggs"),
            PantryItem(user_id=USER, ingredient="tomatoes", quantity="4 pieces", expiry_date=day(3), category="vegetables"),
            UserPreference(user_id=USER, dietary_restrictions="vegan", allergies="soy", onboarding_complete=True),
        )
        answers = iter([
            self.generated("Zz Tomato Frittata", ["eggs", "cheese", "tomatoes", "onion", "salt"]),
            self.generated("Zz Tomato Bruschetta", ["tomatoes", "bread", "olive oil", "garlic", "basil"]),
        ])
        prompts = []

        def answer(offered, prompt):
            prompts.append((offered, prompt))
            return next(answers)

        with patch("routers.recipes.generate_recipe_from_pantry", side_effect=answer):
            made = self.client.post(f"/ai-recipes/{USER}", json={"request": "something with tomatoes"})
        self.assertEqual(made.status_code, 200, made.text)
        self.assertEqual(made.json()["title"], "Zz Tomato Bruschetta")
        offered, prompt = prompts[0]
        self.assertEqual(offered, ["tomatoes"])
        self.assertIn("vegan: no meat", prompt)
        # The retry names the foods at fault and suggests no swap that breaks the soy allergy.
        self.assertIn("used eggs, cheese, which the cook cannot eat (vegan, soy allergy)", prompts[1][1])
        self.assertNotIn("tofu", prompts[1][1])

    def test_swaps_for_the_tapped_ingredient(self):
        [recipe_id] = self.add(Recipe(
            title="Zz Test Carbonara", ingredients="spaghetti,parmesan,egg", instructions="a\n\nb", cooking_time=15, source="MealMatch",
        ))
        self.add(PantryItem(user_id=USER, ingredient="eggs", quantity="6 pieces", expiry_date=day(9), category="eggs"))
        with patch("ai_services.ask_ollama", return_value="Ollama is not running."):
            response = self.client.get(f"/recipes/{recipe_id}/substitutes/{USER}", params={"ingredient": "egg"})
        self.assertEqual(response.status_code, 200, response.text)
        [group] = response.json()["substitutions"]
        self.assertEqual(group["ingredient"], "egg")  # an ingredient the cook has still gets swaps
        self.assertIn("flax egg", [item["name"] for item in group["suggestions"]])


if __name__ == "__main__":
    unittest.main()
