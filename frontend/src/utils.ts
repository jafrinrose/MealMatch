import type { Recipe } from "./types";

export const pantryCategories = ["all", "fruit", "vegetables", "dairy", "meat", "seafood", "eggs", "grains", "bakery", "pantry", "condiments", "snacks", "beverages", "frozen", "other"];
export const quantityUnits = ["piece", "pieces", "jar", "box", "carton", "pack", "bottle", "can", "bag", "bunch", "g", "kg", "ml", "l", "cup", "cups"];
export function splitIngredients(value: string) { return value.split(",").map((item) => item.trim()).filter(Boolean); }
export function titleCase(value: string) { return value.replace(/\b\w/g, (letter) => letter.toUpperCase()); }
// Plural units from suggestions ("2 boxes") map onto the form's unit list instead of falling back to "piece".
const pluralUnits: Record<string, string> = { boxes: "box", jars: "jar", cartons: "carton", packs: "pack", bottles: "bottle", cans: "can", bags: "bag", bunches: "bunch" };
export function parseQuantity(value: string) {
  const match = String(value || "").trim().match(/^(\d+(?:\.\d+)?)\s*(.*)$/);
  const amount = match ? Number(match[1]) : 1;
  const written = match?.[2]?.trim().toLowerCase() || "piece";
  const proposedUnit = pluralUnits[written] || written;
  return { amount: Number.isFinite(amount) ? amount : 1, unit: quantityUnits.includes(proposedUnit) ? proposedUnit : "piece" };
}
export function formatAmount(value: number) { return Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100); }
export function fallbackStepMinutes(instruction: string, index: number, stepCount: number, recipe: Recipe) { const explicit = instruction.match(/(\d+)\s*(?:[-–]\s*(\d+)\s*)?(?:minutes?|mins?)\b/i); if (explicit) return Math.max(1, Math.round((Number(explicit[1]) + Number(explicit[2] || explicit[1])) / 2)); const text = instruction.toLowerCase(); const total = (recipe.prep_time || 10) + recipe.cooking_time; const base = Math.max(1, Math.round(total / Math.max(stepCount, 1))); if (/bake|roast|simmer|braise|boil|cook until|fry/.test(text)) return Math.max(base + 3, Math.round(base * 1.7)); if (/serve|garnish|plate|enjoy/.test(text)) return 1; if (/chop|slice|dice|peel|prepare/.test(text)) return Math.max(2, Math.round(base * .7)); return Math.max(1, base + (index % 3) - 1); }
export function greeting() { const hour = new Date().getHours(); return hour < 12 ? "Good morning," : hour < 17 ? "Good afternoon," : "Good evening,"; }
export function formatClockTime(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? "—" : date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); }
export function recipeDescription(recipe: Recipe) {
  const title = recipe.title.toLowerCase();
  const cuisine = recipe.cuisine && recipe.cuisine.toLowerCase() !== "fusion" ? `${recipe.cuisine} ` : "";
  const highlights = splitIngredients(recipe.ingredients).filter((item) => !/salt|pepper|water|oil/.test(item.toLowerCase())).slice(0, 2).map(titleCase);
  const ingredients = highlights.length ? ` with ${highlights.join(" and ")}` : "";
  if (/pho|ramen|noodle|soup|stew/.test(title)) return `A fragrant ${cuisine}bowl${ingredients}, full of warming, savoury flavour.`;
  if (/salad|slaw/.test(title)) return `A crisp, colourful ${cuisine}salad${ingredients} for a fresh, satisfying meal.`;
  if (/curry/.test(title)) return `A warming ${cuisine}curry${ingredients}, layered with comforting flavour.`;
  if (/stir.?fry/.test(title)) return `A quick, vibrant ${cuisine}stir-fry${ingredients} with a savoury finish.`;
  if (/pasta|lasagne|spaghetti/.test(title)) return `A comforting ${cuisine}pasta dish${ingredients}, made for an easy meal.`;
  if (/baked|roast|grill/.test(title)) return `A simple, savoury ${cuisine}dish${ingredients}, cooked until golden and tender.`;
  return `A satisfying ${cuisine}dish${ingredients}, balanced for an easy, flavourful meal.`;
}
export function categoryEmoji(category: string) { return ({ all: "✦", fruit: "🍎", vegetables: "🥬", dairy: "🥛", meat: "🥩", seafood: "🐟", eggs: "🥚", grains: "🌾", bakery: "🥖", pantry: "🥫", condiments: "🫙", snacks: "🍿", beverages: "🧃", frozen: "❄️", other: "🧺" } as Record<string, string>)[category] || "🧺"; }
export function inferCategory(name: string) {
  const value = name.toLowerCase();
  if (/frozen|ice cream/.test(value)) return "frozen";
  if (/ketchup|mustard|mayonnaise|mayo|relish|dressing|soy sauce|hot sauce|vinegar|salsa|pesto|jam|spread|nutella|peanut butter|nut butter/.test(value)) return "condiments";
  if (/chip|crisp|cracker|biscuit|cookie|popcorn|chocolate|candy|sweet|snack|pretzel/.test(value)) return "snacks";
  if (/juice|water|soda|drink|coffee|tea|smoothie|cola|lemonade/.test(value)) return "beverages";
  if (/apple|banana|berr|grape|lemon|lime|orange|pear|peach|mango|melon|pineapple|kiwi|plum|cherry|coconut|fruit/.test(value)) return "fruit";
  if (/spinach|lettuce|cabbage|salad|tomato|onion|garlic|carrot|pea|broccoli|cucumber|corn|pepper|potato|mushroom|ginger|celery|courgette|zucchini|aubergine|eggplant|asparagus|kale|avocado|vegetable/.test(value)) return "vegetables";
  if (/milk|cheese|yogurt|butter|cream|mozzarella|cheddar|feta|brie|parmesan|dairy/.test(value)) return "dairy";
  if (/chicken|beef|pork|ham|turkey|lamb|sausage|bacon|steak|mince|meat/.test(value)) return "meat";
  if (/fish|salmon|tuna|shrimp|prawn|crab|lobster|sardine|anchov|seafood/.test(value)) return "seafood";
  if (/\begg/.test(value)) return "eggs";
  if (/rice|pasta|noodle|oat|quinoa|couscous|barley|granola|cereal|flour|grain/.test(value)) return "grains";
  if (/bread|baguette|croissant|bun|cake|pastry|tortilla|wrap|pita|muffin/.test(value)) return "bakery";
  if (/oil|bean|lentil|chickpea|soup|stock|broth|tin|canned|spice|salt|sugar|honey|nut|seed|baking powder|yeast/.test(value)) return "pantry";
  return "other";
}
export function normalizedCategory(category: string | undefined, ingredient: string) { const inferred = inferCategory(ingredient); const value = (category || "").toLowerCase().trim(); if (inferred !== "other") return inferred; if (value === "produce") return "vegetables"; if (value === "protein") return "meat"; return pantryCategories.includes(value) ? value : "other"; }
export function expiryStatus(value: string) {
  if (!value) return { label: "No expiry set", urgent: false, expired: false };
  const expiry = new Date(`${value}T23:59:59`);
  if (Number.isNaN(expiry.getTime())) return { label: value, urgent: false, expired: false };
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const expiryDay = new Date(`${value}T00:00:00`);
  const days = Math.round((expiryDay.getTime() - today.getTime()) / 86400000);
  if (days < 0) return { label: "Expired", urgent: true, expired: true };
  if (days === 0) return { label: "Use today", urgent: true, expired: false };
  return { label: `${days} day${days === 1 ? "" : "s"} left`, urgent: days <= 5, expired: false };
}
