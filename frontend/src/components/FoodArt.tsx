import { useState, type CSSProperties } from "react";
import { apiBaseUrl } from "../api";
import { analyseFood, recipeIngredientNames } from "../recipeFilters";
import type { Recipe } from "../types";

const FOOD_EMOJI: Record<string, string> = {
  spinach: "🥬", lettuce: "🥬", cabbage: "🥬", kale: "🥬", celery: "🥬", salad: "🥗", kimchi: "🥬", broccoli: "🥦", cucumber: "🥒", pickle: "🥒",
  bellpepper: "🫑", chili: "🌶️", peppercorn: "🧂", garlic: "🧄", onion: "🧅", springonion: "🧅", shallot: "🧅", mushroom: "🍄", avocado: "🥑",
  potato: "🥔", sweetpotato: "🍠", corn: "🌽", carrot: "🥕", eggplant: "🍆", olive: "🫒", pea: "🫛", ginger: "🫚", tomato: "🍅", zucchini: "🥒",
  herb: "🌿", basil: "🌿", parsley: "🌿", cilantro: "🌿", mint: "🌿", chicken: "🍗", turkey: "🍗", bacon: "🥓", ham: "🥓", pork: "🥓",
  sausage: "🌭", guanciale: "🥓", pancetta: "🥓", prosciutto: "🥓", chorizo: "🌭", salami: "🥓", beef: "🥩", lamb: "🥩", meat: "🥩", fish: "🐟", salmon: "🐟", tuna: "🐟", cod: "🐟", shrimp: "🍤", crab: "🦀", lobster: "🦞",
  squid: "🦑", oyster: "🦪", milk: "🥛", cream: "🥛", yogurt: "🥛", butter: "🧈", cheese: "🧀", egg: "🥚", bite: "🍳", bread: "🍞",
  baguette: "🥖", croissant: "🥐", bagel: "🥯", tortilla: "🫓", pita: "🫓", pancake: "🥞", rice: "🍚", pasta: "🍝", spaghetti: "🍝",
  noodle: "🍜", ramen: "🍜", oat: "🌾", flour: "🌾", cereal: "🥣", granola: "🥣", bean: "🫘", lentil: "🫘", chickpea: "🫘", peanut: "🥜",
  almond: "🌰", nut: "🌰", walnut: "🌰", cashew: "🌰", date: "🌴", strawberry: "🍓", raspberry: "🍓", blackberry: "🫐", blueberry: "🫐",
  berry: "🍓", cherry: "🍒", grape: "🍇", apple: "🍎", pear: "🍐", orange: "🍊", mandarin: "🍊", lemon: "🍋", lime: "🍋", banana: "🍌",
  pineapple: "🍍", mango: "🥭", peach: "🍑", kiwi: "🥝", watermelon: "🍉", melon: "🍈", coconut: "🥥", fruit: "🍎", vegetable: "🥕",
  honey: "🍯", jam: "🍯", salt: "🧂", sugar: "🧂", oil: "🫒", sauce: "🫙", paste: "🫙", ketchup: "🫙", vinegar: "🫙", powder: "🧂",
  seasoning: "🧂", spice: "🧂", stock: "🍲", broth: "🍲", syrup: "🍯", juice: "🧃", water: "💧", coffee: "☕", tea: "🍵",
  chocolate: "🍫", bar: "🍫", cookie: "🍪", cake: "🍰", mix: "🥜", snack: "🍿", popcorn: "🍿", tofu: "🧊", pizza: "🍕",
};

function ingredientEmoji(name: string) {
  const food = analyseFood(name, "pantry");
  const key = food.identity.includes("sweet") && food.head === "potato" ? "sweetpotato" : food.head;
  if (food.derived && FOOD_EMOJI[food.derived]) return FOOD_EMOJI[food.derived];
  return FOOD_EMOJI[key] || food.words.map((word) => FOOD_EMOJI[word]).find(Boolean) || "🥫";
}

export function IngredientEmoji({ name, small = false }: { name: string; small?: boolean }) {
  return <span className={`ingredient-emoji ${small ? "small" : ""}`} aria-hidden="true"><span>{ingredientEmoji(name)}</span></span>;
}

export function RecipeArtwork({ recipe, lazy = false }: { recipe: Recipe; lazy?: boolean }) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  // Web photos come through the backend: on some networks the browser cannot reach TheMealDB itself.
  const photo = /^https?:\/\//.test(recipe.image_url || "") ? `${apiBaseUrl}/recipes/${recipe.id}/photo` : recipe.image_url || "";
  const src = failed ? "" : photo;
  if (!src) return <span className="recipe-art"><FoodArtwork recipe={recipe} /></span>;
  // A cached image can finish before React attaches onLoad; check completeness on mount too.
  return <img ref={(element) => { if (element?.complete && element.naturalWidth > 0 && !loaded) setLoaded(true); }} className={`recipe-photo ${loaded ? "is-loaded" : ""}`} src={src} alt={recipe.title} loading={lazy ? "lazy" : "eager"} referrerPolicy="no-referrer" onLoad={() => setLoaded(true)} onError={() => setFailed(true)} />;
}

// Recipes without a photo (every AI recipe) show their main foods as emojis on a plate:
// drawn at once, with no image model (user testing, design iteration 3).
const FOOD_ART_PALETTES = [
  ["#fde8d4", "#f4b27f"], ["#e4f2dc", "#9fd08f"], ["#efe5f7", "#c3a3e0"],
  ["#fff2c8", "#f0c95c"], ["#dff1f3", "#8fcad1"], ["#fbe1e5", "#eb9dab"],
];
// Seasonings say nothing about the dish, so they are not drawn; baking basics only when nothing else is.
const QUIET_EMOJI = new Set(["🥫", "🧂", "💧", "🫙", "🫒"]);
const BASIC_EMOJI = new Set(["🌾", "🧈"]);

// The foods the title names come first ("Strawberry Banana Pancakes": 🍓 on the plate, not flour).
function recipeFoodEmojis(recipe: Recipe) {
  const names = recipeIngredientNames(recipe);
  const titleFoods = new Set(recipe.title.split(/[^a-zA-Z]+/).filter(Boolean).map((word) => analyseFood(word, "recipe").head));
  const rank = (name: string) => {
    const emoji = ingredientEmoji(name);
    if (QUIET_EMOJI.has(emoji)) return 3;
    if (titleFoods.has(analyseFood(name, "recipe").head)) return 0;
    return BASIC_EMOJI.has(emoji) ? 2 : 1;
  };
  const ranked = names.map((name, index) => ({ emoji: ingredientEmoji(name), order: rank(name) * 100 + index })).sort((a, b) => a.order - b.order);
  const telling = Array.from(new Set(ranked.filter((item) => !QUIET_EMOJI.has(item.emoji)).map((item) => item.emoji)));
  return (telling.length ? telling : ["🍽️"]).slice(0, 4);
}

function FoodArtwork({ recipe }: { recipe: Recipe }) {
  const seed = Array.from(recipe.title).reduce((total, letter) => total + letter.charCodeAt(0), 0);
  const [paper, accent] = FOOD_ART_PALETTES[seed % FOOD_ART_PALETTES.length];
  const [main, ...others] = recipeFoodEmojis(recipe);
  return <span className="food-art" style={{ "--fa-paper": paper, "--fa-accent": accent } as CSSProperties} aria-hidden="true">
    <span className="food-art-plate"><i className="food-art-main">{main}</i></span>
    {others.map((emoji, index) => <i className={`food-art-side side-${index + 1}`} key={emoji}>{emoji}</i>)}
  </span>;
}
