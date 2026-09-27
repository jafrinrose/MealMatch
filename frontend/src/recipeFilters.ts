/**
 * Shared, deterministic recipe filtering. No model-generated search results.
 *
 * Food names are reduced to a head food, identity modifiers (coconut milk is not
 * milk), variety modifiers (red onion is still onion) and an optional derived
 * product (chicken stock is not chicken). The rules mirror backend/ingredient_matching.py.
 */
type SearchableRecipe = {
  title: string; ingredients: string; cuisine: string;
  cooking_time: number; prep_time?: number; total_time?: number;
  ingredient_details?: { name: string }[];
};

const SYNONYMS: [RegExp, string][] = [
  [/\b(?:green onions?|scallions?|spring onions?)\b/g, "springonion"],
  [/\b(?:sweet corn|corn on the cob|corn kernels?)\b/g, "corn"],
  [/\bcourgettes?\b/g, "zucchini"],
  [/\baubergines?\b/g, "eggplant"],
  [/\b(?:coriander leaves|fresh coriander|cilantro)\b/g, "cilantro"],
  [/\bprawns?\b/g, "shrimp"],
  [/\byoghurt\b/g, "yogurt"],
  [/\b(?:chillies|chilies|chilli|chile|chiles)\b/g, "chili"],
  [/\bgarbanzo(?: beans?)?\b/g, "chickpea"],
  [/\bmayo\b/g, "mayonnaise"],
  [/\bparmigiano(?: reggiano)?\b/g, "parmesan"],
  [/&/g, " and "],
];
const set = (value: string) => new Set(value.split(" "));
const DESCRIPTORS = set("fresh freshly chopped sliced diced minced ground large small medium big organic grass fed free range boneless skinless lean extra virgin raw ripe frozen canned tinned dried whole halved peeled crushed finely roughly thinly cubed grated shredded cooked uncooked leftover plain unsalted salted low fat nonfat skim skimmed full reduced sodium mini of a the to taste for serving optional pinch handful bunch heavy double single light whipped whipping softened melted beaten packed fine coarse baby young new wild boiled roasted toasted smoked and or into about some few");
const PARTS = set("breast thigh drumstick wing leg fillet filet loin sirloin tenderloin flank chop cutlet shank rib brisket cube chunk piece strip slice ring wedge head stalk stick floret leaf sprig clove steak mince segment half quarter");
const DERIVED = set("stock broth bouillon sauce paste powder oil flour extract essence seasoning flake vinegar syrup jam jelly puree ketchup juice zest chip crisp fry fries gravy dressing spread cube");
const DERIVABLE_FROM_WHOLE = set("juice zest");
const IDENTITY = set("sweet coconut almond oat soy peanut cashew sour cream ice cottage goat sesame rice kidney evaporated condensed powdered");
const GENERIC = set("vegetable fruit produce snack food mix ingredient spice herb grocery bar item");
const CHEESES = set("parmesan cheddar mozzarella feta brie halloumi ricotta gouda gruyere pecorino mascarpone camembert emmental provolone manchego stilton paneer");
const PEPPER_WORDS = set("pepper peppercorn capsicum");
const CHILI_TRIGGERS = set("chili jalapeno cayenne serrano habanero chipotle poblano");
const CHILI_TYPES = new Set([...CHILI_TRIGGERS, "thai", "bird", "scotch", "bonnet"]);
const BELL_WORDS = set("bell sweet red green yellow orange capsicum");

function singular(word: string): string {
  if (word.length <= 3 || /(ss|us|is)$/.test(word)) return word;
  if (word.endsWith("ies")) return `${word.slice(0, -3)}y`;
  if (/(oes|shes|ches|xes|zes)$/.test(word)) return word.slice(0, -2);
  if (word === "leaves") return "leaf";
  if (word === "halves") return "half";
  if (word === "loaves") return "loaf";
  if (word.endsWith("s")) return word.slice(0, -1);
  return word;
}

function plain(value: string): string {
  return String(value || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/-/g, " ");
}

/** Lower-case, accent-free, singular words. */
export function words(value: string): string[] {
  return plain(value).match(/[\p{L}\p{N}]+/gu)?.map(singular) || [];
}

type FoodName = { head: string; derived: string | null; identity: string[]; varieties: string[]; generic: boolean; words: string[] };

const analysisCache = new Map<string, FoodName>();
const matchCache = new Map<string, boolean>();

/** Names repeat constantly while scoring every recipe against the pantry, so results are cached. */
export function analyseFood(name: string, context: "recipe" | "pantry" = "recipe"): FoodName {
  const key = `${context}|${name}`;
  let cached = analysisCache.get(key);
  if (!cached) {
    cached = analyseUncached(name, context);
    if (analysisCache.size > 20000) analysisCache.clear();
    analysisCache.set(key, cached);
  }
  return cached;
}

function analyseUncached(name: string, context: "recipe" | "pantry"): FoodName {
  let text = plain(name);
  for (const [pattern, replacement] of SYNONYMS) text = text.replace(pattern, replacement);
  let tokens = (text.match(/[a-z]+/g) || []).map(singular).filter((word) => !DESCRIPTORS.has(word));
  let derived = [...tokens].reverse().find((word) => DERIVED.has(word)) ?? null;
  if (derived && tokens.length > 1) tokens = tokens.filter((word) => word !== derived);
  else if (derived) derived = null; // "oil" on its own is simply oil
  if (tokens.length > 1) {
    const kept = tokens.filter((word) => !PARTS.has(word));
    tokens = kept.length ? kept : tokens.slice(-1);
  }
  if (tokens.length === 1 && (tokens[0] === "steak" || tokens[0] === "mince")) tokens = ["beef"];
  const empty = { identity: [], varieties: [], generic: false, words: [] as string[] };
  if (!tokens.length) return { head: "", derived, ...empty };

  // Peppers: one word, three different foods.
  const hasPepper = tokens.some((word) => PEPPER_WORDS.has(word));
  if (hasPepper || tokens.some((word) => CHILI_TRIGGERS.has(word))) {
    const chili = tokens.filter((word) => CHILI_TYPES.has(word));
    if (derived === "flake" || chili.length) {
      const rest = tokens.filter((word) => !PEPPER_WORDS.has(word) && !CHILI_TYPES.has(word) && !BELL_WORDS.has(word));
      return { head: "chili", derived, identity: [], varieties: [...chili.filter((word) => word !== "chili"), ...rest], generic: false, words: rest };
    }
    if (hasPepper) {
      if (tokens.some((word) => ["black", "white", "peppercorn"].includes(word))) return { head: "peppercorn", derived, ...empty };
      if (tokens.some((word) => BELL_WORDS.has(word))) return { head: "bellpepper", derived, ...empty };
      return { head: context === "recipe" ? "peppercorn" : "bellpepper", derived, ...empty };
    }
  }

  if (tokens.some((word) => CHEESES.has(word)) && tokens.at(-1) !== "cheese") tokens = [...tokens, "cheese"];
  const head = tokens.at(-1)!;
  const modifiers = tokens.slice(0, -1);
  return {
    head, derived,
    identity: modifiers.filter((word) => IDENTITY.has(word)).sort(),
    varieties: modifiers.filter((word) => !IDENTITY.has(word)),
    generic: GENERIC.has(head),
    words: tokens,
  };
}

function foodsMatch(recipeFood: FoodName, pantryFood: FoodName): boolean {
  if (!recipeFood.head || recipeFood.head !== pantryFood.head) return false;
  if (recipeFood.derived !== pantryFood.derived && !(recipeFood.derived && DERIVABLE_FROM_WHOLE.has(recipeFood.derived) && pantryFood.derived === null)) return false;
  if (recipeFood.generic || pantryFood.generic) return recipeFood.words.join(" ") === pantryFood.words.join(" ");
  if (recipeFood.identity.join(" ") !== pantryFood.identity.join(" ")) return false;
  if (recipeFood.varieties.length && pantryFood.varieties.length && !recipeFood.varieties.some((word) => pantryFood.varieties.includes(word))) return false;
  return true;
}

/** Can this pantry item stand in for the recipe ingredient? */
export function pantryMatch(recipeIngredient: string, pantryIngredient: string): boolean {
  const key = `${recipeIngredient}|${pantryIngredient}`;
  let result = matchCache.get(key);
  if (result === undefined) {
    result = foodsMatch(analyseFood(recipeIngredient, "recipe"), analyseFood(pantryIngredient, "pantry"));
    if (matchCache.size > 100000) matchCache.clear();
    matchCache.set(key, result);
  }
  return result;
}

/** Does this recipe ingredient *be* the searched food (not something made from it)? */
export function ingredientMatches(name: string, query: string): boolean {
  return foodsMatch(analyseFood(name, "recipe"), analyseFood(query, "recipe"));
}

// Searching a family finds its members: "pasta" finds spaghetti, "fish" finds salmon.
const FISH = "fish salmon tuna cod haddock tilapia mackerel sardine anchovy trout bass halibut snapper pollock hake catfish swordfish";
const FOOD_FAMILIES: Record<string, string[]> = {
  pasta: "pasta spaghetti penne macaroni fusilli linguine fettuccine fettuccini tagliatelle lasagne lasagna rigatoni orzo ravioli tortellini farfalle pappardelle".split(" "),
  noodle: "noodle ramen udon soba vermicelli".split(" "),
  fish: FISH.split(" "),
  seafood: `${FISH} shrimp crab lobster mussel clam oyster scallop squid octopus calamari seafood`.split(" "),
  meat: "meat beef pork lamb chicken turkey bacon ham sausage veal duck mutton chorizo salami pepperoni prosciutto".split(" "),
  poultry: "poultry chicken turkey duck".split(" "),
  cheese: ["cheese", ...CHEESES],
  legume: "bean lentil chickpea".split(" "),
  bean: "bean lentil chickpea".split(" "),
};
const QUERY_NOISE = set("with and or recipe dish meal food a an the some");

type SearchTerm = { text: string; family: string[] | null };

function searchTerms(query: string): SearchTerm[] {
  const tokens = words(query).filter((word) => !QUERY_NOISE.has(word));
  if (!tokens.length) return [];
  // A multi-word food ("sweet potato", "chicken stock") is one term, not two.
  if (tokens.length > 1 && !tokens.some((word) => FOOD_FAMILIES[word])) {
    const whole = analyseFood(tokens.join(" "));
    if (whole.head && (whole.derived || whole.identity.length || whole.head !== tokens.at(-1))) return [{ text: tokens.join(" "), family: null }];
  }
  return tokens.map((word) => ({ text: word, family: FOOD_FAMILIES[word] ?? null }));
}

/** The recipe's ingredient names, from its measured list when it has one. */
export function recipeIngredientNames(recipe: SearchableRecipe): string[] {
  return recipe.ingredient_details?.length
    ? recipe.ingredient_details.map((item) => item.name)
    : recipe.ingredients.split(",").map((item) => item.trim()).filter(Boolean);
}

/** 0 = no match, higher = better (title matches outrank ingredient matches). */
export function recipeSearchScore(recipe: SearchableRecipe, query: string): number {
  const terms = searchTerms(query.trim());
  if (!terms.length) return 1;
  const titleWords = words(recipe.title);
  const title = ` ${titleWords.join(" ")} `;
  const cuisine = words(recipe.cuisine);
  const ingredients = recipeIngredientNames(recipe);
  const phrase = words(query).filter((word) => !QUERY_NOISE.has(word)).join(" ");
  if (terms.length > 1 && (title.includes(` ${phrase} `) || ingredients.some((ingredient) => ingredientMatches(ingredient, phrase)))) {
    return title.includes(` ${phrase} `) ? 3 * terms.length : terms.length;
  }
  let score = 0;
  for (const term of terms) {
    const candidates = term.family ?? [term.text];
    const inTitle = candidates.some((food) => title.includes(` ${words(food).join(" ")} `));
    const inCuisine = candidates.some((food) => cuisine.includes(food));
    const inIngredients = candidates.some((food) => ingredients.some((ingredient) => ingredientMatches(ingredient, food)));
    if (!inTitle && !inCuisine && !inIngredients) return 0;
    score += inTitle ? 3 : inCuisine ? 2 : 1;
  }
  return score;
}

export function recipeMatchesSearch(recipe: SearchableRecipe, query: string): boolean {
  return recipeSearchScore(recipe, query) > 0;
}

export function recipeTotalMinutes(recipe: Pick<SearchableRecipe, "total_time" | "prep_time" | "cooking_time">): number {
  if (typeof recipe.total_time === "number" && Number.isFinite(recipe.total_time) && recipe.total_time >= 0) return recipe.total_time;
  return Math.max(0, recipe.prep_time ?? 10) + Math.max(0, recipe.cooking_time || 0);
}

export function pantryHasIngredient(name: string, pantryNames: string[]): boolean {
  return pantryNames.some((pantryName) => pantryMatch(name, pantryName));
}
