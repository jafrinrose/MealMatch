import unittest

from ingredient_matching import ingredient_is_food, pantry_match


class PantryMatchTests(unittest.TestCase):
    def test_same_food_in_different_words(self):
        for recipe, pantry in [
            ("chicken", "chicken breast"), ("chicken thighs", "chicken"), ("eggs", "egg"),
            ("tomatoes", "grape tomato"), ("onion", "red onion"), ("beef", "sliced grass-fed beef sirloin"),
            ("red bell pepper", "sweet pepper"), ("garlic cloves", "garlic"), ("lemon juice", "lemon"),
            ("cheddar cheese", "cheese"), ("feta", "feta cheese"), ("scallions", "green onion"),
            ("prawns", "shrimp"), ("chili flakes", "crushed red pepper flakes"), ("jalapeno", "jalapeno"),
            ("heavy cream", "whipped cream"), ("courgette", "zucchini"), ("potatoes", "potato"),
        ]:
            with self.subTest(recipe=recipe, pantry=pantry):
                self.assertTrue(pantry_match(recipe, pantry))

    def test_different_foods_that_share_words(self):
        for recipe, pantry in [
            ("black pepper", "pepper"), ("pepper", "pepper"), ("cherry tomato", "cherry"),
            ("chicken", "chicken stock"), ("chicken stock", "chicken"), ("shrimp", "shrimp paste"),
            ("olive oil", "kalamata olives"), ("coconut milk", "milk"), ("sweet potato", "potatoes"),
            ("peanut butter", "butter"), ("cream cheese", "cheese"), ("sour cream", "whipped cream"),
            ("parmesan", "brie cheese"), ("eggs", "egg bites"), ("egg noodles", "eggs"),
            ("lemon", "lemon juice"), ("garlic powder", "garlic"), ("spring onion", "red onion"),
            ("carrot", "vegetables"), ("strawberry", "fruits"), ("tomato paste", "tomato"),
        ]:
            with self.subTest(recipe=recipe, pantry=pantry):
                self.assertFalse(pantry_match(recipe, pantry))

    def test_search_food_identity(self):
        self.assertTrue(ingredient_is_food("chicken thighs", "chicken"))
        self.assertFalse(ingredient_is_food("chicken stock", "chicken"))
        self.assertFalse(ingredient_is_food("shrimp paste", "shrimp"))
        self.assertFalse(ingredient_is_food("thai basil", "chili"))


if __name__ == "__main__":
    unittest.main()
