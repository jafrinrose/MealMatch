import test from "node:test";
import assert from "node:assert/strict";
import { ingredientMatches, recipeMatchesSearch, recipeSearchScore, recipeTotalMinutes, pantryHasIngredient, pantryMatch } from "../src/recipeFilters.ts";

const recipe = { title: "Shrimp rice", cuisine: "Asian", ingredients: "shrimp,rice,chicken stock", cooking_time: 20, prep_time: 0 };

test("search requires the food itself, not a product made from it or a substring", () => {
  assert.equal(recipeMatchesSearch(recipe, "chicken"), false);
  assert.equal(recipeMatchesSearch(recipe, "chicken stock"), true);
  assert.equal(recipeMatchesSearch({ ...recipe, ingredients: "champignon,rice" }, "ham"), false);
  assert.equal(recipeMatchesSearch({ ...recipe, ingredients: "chicken breast,rice" }, " CHICKEN "), true);
  assert.equal(recipeMatchesSearch({ ...recipe, title: "Chicken rice" }, "chicken rice"), true);
  assert.equal(recipeMatchesSearch({ ...recipe, title: "Panang curry", ingredients: "shrimp paste,coconut milk" }, "shrimp"), false);
  assert.equal(ingredientMatches("tomatoes", "tomato"), true);
});

test("food families and multi-word foods", () => {
  const spaghetti = { ...recipe, title: "Midnight spaghetti", ingredients: "spaghetti,garlic,olive oil" };
  assert.equal(recipeMatchesSearch(spaghetti, "pasta"), true);
  assert.equal(recipeMatchesSearch({ ...recipe, title: "Baked salmon", ingredients: "salmon,lemon" }, "fish"), true);
  assert.equal(recipeMatchesSearch({ ...recipe, title: "Salad", ingredients: "cherry tomatoes,basil" }, "cherry tomato"), true);
  assert.equal(recipeMatchesSearch({ ...recipe, title: "Mash", ingredients: "potatoes,butter" }, "sweet potato"), false);
  assert.ok(recipeSearchScore({ ...recipe, title: "Chicken curry", ingredients: "chicken,rice" }, "chicken") > recipeSearchScore({ ...recipe, title: "Paella", ingredients: "chicken,rice" }, "chicken"));
});

test("total time preserves zero prep and trusts the stored total", () => {
  assert.equal(recipeTotalMinutes(recipe), 20);
  assert.equal(recipeTotalMinutes({ ...recipe, total_time: 35 }), 35);
  assert.equal(recipeTotalMinutes({ cooking_time: 15 }), 25);
});

test("pantry matching handles qualified names without matching different foods", () => {
  assert.equal(pantryHasIngredient("chicken", ["chicken breast"]), true);
  assert.equal(pantryHasIngredient("chicken", ["chicken stock"]), false);
  assert.equal(pantryHasIngredient("egg", ["eggs"]), true);
  assert.equal(pantryHasIngredient("rice", []), false);
  assert.equal(pantryMatch("black pepper", "pepper"), false);
  assert.equal(pantryMatch("red bell pepper", "sweet pepper"), true);
  assert.equal(pantryMatch("cherry tomato", "cherry"), false);
  assert.equal(pantryMatch("beef", "sliced grass-fed beef sirloin"), true);
  assert.equal(pantryMatch("carrot", "vegetables"), false);
  assert.equal(pantryMatch("lemon juice", "lemon"), true);
});
