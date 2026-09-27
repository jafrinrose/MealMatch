export type Tab = "home" | "pantry" | "recipes" | "chat" | "settings";
export type User = { id: number; name: string };

export type PantryItem = {
  id: number;
  user_id: number;
  ingredient: string;
  quantity: string;
  expiry_date: string;
  category: string;
  expiry_estimated?: boolean;
};

type ScoreDetails = {
  final_score: number;
  ingredient_match_score: number;
  preference_score: number;
  dietary_score: number;
  cooking_time_score: number;
  variety_score: number;
  matched_ingredients: string[];
  missing_ingredients?: string[];
  expiring_matched_ingredients?: string[];
  use_soon_used?: { ingredient: string; days_left: number }[];
  expiry_score?: number;
  cuisine_score?: number;
  semantic_score?: number;
  allergy_conflicts?: string[];
  dietary_conflict?: string | null;
  eligible?: boolean;
  explanation?: string;
};

export type IngredientDetail = { name: string; amount: number; unit: string };
type StepDetail = { instruction: string; minutes: number };
export type Substitution = { ingredient: string; suggestions: { name: string; reason: string; in_pantry?: boolean }[] };
export type ShoppingItem = { id: number; user_id: number; recipe_id: number | null; ingredient: string; quantity: string; checked: boolean };
export type HomeInsights = {
  meals_cooked: number;
  meals_this_week: number;
  last_meal: string | null;
  top_ingredient: string | null;
  ingredients_used: number;
  rescued_items: number;
  rescue_rate: number;
  estimated_savings: number;
  last_rescue_count: number;
  last_estimated_savings: number;
  rescue_events?: { ingredient: string; recipe_title: string; quantity_used: string; days_to_expiry: number; session_id: number; estimated_grams?: number }[];
  estimated_grams_saved?: number;
  estimated_co2e_kg?: number;
  weekly_rescues?: { week_start: string; count: number }[];
  at_risk_count?: number;
  at_risk_items?: { ingredient: string; days_left: number }[];
  rescue_window_days?: number;
};
export type RecipeOpenOptions = { swaps?: boolean };
export type AiIdeas = { request: string; ids: number[] };
// One AI feature from GET /health, with what to do when it is not ready.
export type ModelFeature = { feature: string; model: string; ready: boolean; fix: string };

export type Recipe = {
  id: number;
  title: string;
  ingredients: string;
  instructions: string;
  cooking_time: number;
  difficulty: string;
  cuisine: string;
  calories: number;
  score_details?: ScoreDetails;
  ingredient_details?: IngredientDetail[];
  instruction_steps?: string[];
  step_details?: StepDetail[];
  prep_time?: number;
  total_time?: number;
  servings?: number;
  image_url?: string;
  source?: string;
  source_id?: string;
  saved?: boolean;
  rank?: number;
  // Saved diets this recipe breaks. Such recipes are listed only after every recipe that fits.
  diet_conflicts?: { diet: string; ingredients: string[] }[];
};

export type CookingSession = {
  id: number;
  user_id: number;
  recipe_id: number;
  servings: number;
  started_at: string;
  ready_at: string;
  status: string;
  current_step: number;
  recipe: Recipe;
  messages: { id: number; role: "user" | "assistant"; text: string; created_at: string }[];
};

export type UserPreferences = {
  user_id: number;
  dietary_restrictions: string[];
  allergies: string[];
  disliked_ingredients: string[];
  preferred_cuisines: string[];
  max_cooking_time: number | null;
  skill_level: string;
  onboarding_complete: boolean;
};

export type DetectedIngredient = {
  ingredient: string;
  quantity: string;
  expiry_date: string;
  category?: string;
  confidence?: number;
  detection_id?: string;
  source?: string;
  visible_text?: string;
  semantic_alternatives?: string[];
};
