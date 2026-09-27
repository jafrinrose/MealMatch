import { Fragment, useState, type CSSProperties } from "react";
import { pantryHasIngredient, recipeIngredientNames, recipeSearchScore, recipeTotalMinutes } from "../recipeFilters";
import type { RecipeOpenOptions, AiIdeas, Recipe, UserPreferences } from "../types";
import { titleCase } from "../utils";
import { PageHeader, EmptyState, Icon } from "../components/ui";
import { IngredientEmoji } from "../components/FoodArt";
import { RecipeCard } from "../components/RecipeCard";

export function RecipesScreen({ recipes, preferences, onOpenRecipe, onToggleSaved, aiIdeas, aiGenerating, aiError, onGenerate, onClearIdeas, onAddMissing, focusIngredients, onClearFocus }: { recipes: Recipe[]; preferences: UserPreferences; onOpenRecipe: (recipe: Recipe, options?: RecipeOpenOptions) => void; onToggleSaved: (recipe: Recipe) => void; aiIdeas: AiIdeas | null; aiGenerating: boolean; aiError: string; onGenerate: (request: string) => Promise<void>; onClearIdeas: () => void; onAddMissing: (recipe: Recipe) => Promise<boolean>; focusIngredients: string[] | null; onClearFocus: () => void }) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<"recommended" | "match" | "quick" | "saved">("recommended");
  const [cuisine, setCuisine] = useState("all");
  const [maxTime, setMaxTime] = useState("all");
  const [availability, setAvailability] = useState<"any" | "complete" | "mostly">("any");
  const [generatorOpen, setGeneratorOpen] = useState(() => aiGenerating || Boolean(aiError));
  const [generatorRequest, setGeneratorRequest] = useState("");
  const byId = new Map(recipes.map((recipe) => [recipe.id, recipe]));
  const generatedOptions = (aiIdeas?.ids || []).map((id) => byId.get(id)).filter((recipe): recipe is Recipe => Boolean(recipe));
  const cuisines = Array.from(new Set(recipes.map((recipe) => recipe.cuisine).filter(Boolean))).sort();
  const query = search.trim();
  // From "Use soon" on the home screen: recipes that use those foods, the most urgent first.
  const focus = focusIngredients || [];
  const usesFocus = (recipe: Recipe) => {
    const names = recipeIngredientNames(recipe);
    return focus.filter((food) => names.some((name) => pantryHasIngredient(name, [food])));
  };
  const focusScore = (used: string[]) => used.reduce((total, food) => total + (focus.length - focus.indexOf(food)), 0);
  const filtered = recipes
    .map((recipe) => ({ recipe, relevance: query ? recipeSearchScore(recipe, query) : 1, used: focus.length ? usesFocus(recipe) : [] }))
    .filter(({ used }) => !focus.length || used.length > 0)
    .filter(({ recipe, relevance }) => {
      const matchesSaved = sort !== "saved" || recipe.saved;
      const matchesCuisine = cuisine === "all" || recipe.cuisine.toLowerCase() === cuisine.toLowerCase();
      const matchesTime = maxTime === "all" || recipeTotalMinutes(recipe) <= Number(maxTime);
      const matchScore = recipe.score_details?.ingredient_match_score || 0;
      const matchesAvailability = availability === "any" || (availability === "complete" ? matchScore >= 0.999 : matchScore >= 0.6);
      return relevance > 0 && matchesSaved && matchesCuisine && matchesTime && matchesAvailability;
    })
    .sort((a, b) => {
      // Saved diets are hard filters: a recipe that breaks one never comes before one that fits.
      const dietOrder = Number(Boolean(a.recipe.diet_conflicts?.length)) - Number(Boolean(b.recipe.diet_conflicts?.length));
      if (dietOrder) return dietOrder;
      if (focus.length && focusScore(b.used) !== focusScore(a.used)) return focusScore(b.used) - focusScore(a.used);
      if (query && b.relevance !== a.relevance) return b.relevance - a.relevance;
      if (sort === "quick") return recipeTotalMinutes(a.recipe) - recipeTotalMinutes(b.recipe);
      if (sort === "match") return (b.recipe.score_details?.ingredient_match_score || 0) - (a.recipe.score_details?.ingredient_match_score || 0);
      return 0;
    });
  const usedFocus = new Map(filtered.map(({ recipe, used }) => [recipe.id, used]));
  const shown = filtered.map(({ recipe }) => recipe);
  const firstOutsideDiet = shown.findIndex((recipe) => recipe.diet_conflicts?.length);
  const dietNames = preferences.dietary_restrictions.map(titleCase).join(", ");
  const filtersActive = cuisine !== "all" || maxTime !== "all" || availability !== "any" || Boolean(query);

  function generate() {
    const request = generatorRequest.trim();
    if (aiGenerating || !request) return;
    void onGenerate(request);
  }

  const generating = aiGenerating;
  const placeholders = generating ? Math.max(0, 3 - generatedOptions.length) : 0;
  return (
    <div className="screen recipes-screen">
      <PageHeader eyebrow="Cook with what you have" title="Recipes" subtitle="Fresh ideas matched to your kitchen" action={<button className="primary-button header-button ai-recipe-button" onClick={() => setGeneratorOpen(!generatorOpen)}><Icon name="sparkles" /> Create with AI</button>} />
      <button className="primary-button mobile-ai-recipe-button" onClick={() => setGeneratorOpen(!generatorOpen)}><Icon name="sparkles" /> Create a pantry recipe with AI</button>
      {generatorOpen && <section className="ai-generator">
        <div className="generator-intro"><span><Icon name="sparkles" /></span><div><strong>What are you in the mood for?</strong><small>Three ideas for your craving, using only the pantry foods that belong in the dish.</small><small className="generator-rules">{preferences.dietary_restrictions.length || preferences.allergies.length ? `Following your saved rules: ${[...preferences.dietary_restrictions, ...preferences.allergies.map((item) => `${item} allergy`)].map(titleCase).join(", ")}` : "You can add dietary preferences and allergies in Settings."}</small></div></div>
        <div className="generator-composer"><input aria-label="Describe the recipes you want" placeholder="e.g. a quick chicken dinner, no oven" value={generatorRequest} onChange={(event) => setGeneratorRequest(event.target.value)} onKeyDown={(event) => event.key === "Enter" && void generate()} /><button disabled={generating || !generatorRequest.trim()} onClick={() => void generate()}>{generating ? <><i className="button-spinner" /> Creating idea {Math.min(generatedOptions.length + 1, 3)} of 3…</> : "Show 3 ideas"}</button></div>
        {aiError && <p className="generator-error" role="alert"><Icon name="alert" />{aiError}</p>}
      </section>}
      {(generatedOptions.length > 0 || generating) && <section className="ai-choice-section" aria-label="Generated recipe choices" aria-busy={generating}>
        <div className="ai-choice-heading"><div><p className="eyebrow">Made for “{aiIdeas?.request}”</p><h2>What sounds good?</h2></div>{!generating && <button className="ai-choice-clear" onClick={onClearIdeas}><Icon name="close" /> Clear ideas</button>}</div>
        <div className="ai-choice-grid">
          {generatedOptions.map((recipe, index) => <AiChoiceCard key={recipe.id} recipe={recipe} index={index} onOpen={(options) => onOpenRecipe(recipe, options)} onAddMissing={() => onAddMissing(recipe)} />)}
          {Array.from({ length: placeholders }, (_, index) => <div className="ai-title-card is-skeleton" key={`skeleton-${index}`} aria-hidden="true"><div><span /><h3 /><small /></div></div>)}
        </div>
      </section>}
      {focus.length > 0 && <section className="use-soon-focus" aria-label="Recipes for food to use soon">
        <div><p className="eyebrow"><Icon name="alert" /> Use soon</p><h2>Recipes that use your expiring food</h2><p>{shown.length ? `${shown.length} recipe${shown.length === 1 ? "" : "s"}, the ones that use the most urgent food first.` : "No recipes use these yet. Try creating one with AI."}</p></div>
        <div className="use-soon-chips">{focus.slice(0, 8).map((food) => <span key={food}><IngredientEmoji name={food} small />{titleCase(food)}</span>)}{focus.length > 8 && <span>+{focus.length - 8} more</span>}</div>
        <button onClick={onClearFocus}><Icon name="close" /> Show all recipes</button>
      </section>}
      <div className="search-field"><Icon name="search" /><input aria-label="Search recipes" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search a dish, ingredient or cuisine…" />{search && <button className="search-clear" aria-label="Clear search" onClick={() => setSearch("")}><Icon name="close" /></button>}</div>
      <div className="recipe-filters">
        <label><span>Cuisine</span><select value={cuisine} onChange={(event) => setCuisine(event.target.value)}><option value="all">All cuisines</option>{cuisines.map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
        <label><span>Total time</span><select value={maxTime} onChange={(event) => setMaxTime(event.target.value)}><option value="all">Any time</option><option value="20">20 minutes or less</option><option value="30">30 minutes or less</option><option value="45">45 minutes or less</option><option value="60">60 minutes or less</option></select></label>
        <label><span>Pantry availability</span><select value={availability} onChange={(event) => setAvailability(event.target.value as "any" | "complete" | "mostly")}><option value="any">Any match</option><option value="complete">Everything available</option><option value="mostly">60% or more available</option></select></label>
        {filtersActive && <button onClick={() => { setCuisine("all"); setMaxTime("all"); setAvailability("any"); setSearch(""); }}><Icon name="close" /> Clear all</button>}
      </div>
      <div className="segmented-control">
        {(["recommended", "match", "quick", "saved"] as const).map((option) => <button key={option} className={sort === option ? "active" : ""} onClick={() => setSort(option)}>{option === "match" ? "Best match" : option === "quick" ? "Quickest" : option === "saved" ? `Saved recipes (${recipes.filter((recipe) => recipe.saved).length})` : "Recommended"}</button>)}
      </div>
      {filtersActive && <p className="results-count" role="status">{shown.length} recipe{shown.length === 1 ? "" : "s"}{query ? <> for “{query}”</> : ""}</p>}
      {sort === "saved" && <div className="collection-heading"><p className="eyebrow">Your collection</p><h2>Saved recipes</h2></div>}
      <div className="recipe-grid">
        {shown.map((recipe, index) => <Fragment key={recipe.id}>
          {index === firstOutsideDiet && <div className="diet-fallback-divider" role="note"><strong>{index > 0 ? `That’s every recipe here that fits your ${dietNames} preference.` : `No recipes here fit your ${dietNames} preference.`}</strong><span>These break it, so check the ingredients before you cook.</span></div>}
          <RecipeCard recipe={recipe} index={index} onClick={() => onOpenRecipe(recipe)} onToggleSaved={() => onToggleSaved(recipe)} highlight={focus.length ? usedFocus.get(recipe.id) : undefined} />
        </Fragment>)}
      </div>
      {shown.length === 0 && !focus.length && <EmptyState icon={sort === "saved" ? "bookmark" : "search"} title={sort === "saved" ? "No saved recipes yet" : "No recipes found"} text={sort === "saved" ? "Tap the bookmark on a recipe to keep it here for later." : "Try another ingredient, cuisine, or recipe name."} />}
    </div>
  );
}

// An AI idea is its name, time and pantry fit: no picture, so it shows the moment it is written.
function AiChoiceCard({ recipe, index, onOpen, onAddMissing }: { recipe: Recipe; index: number; onOpen: (options?: RecipeOpenOptions) => void; onAddMissing: () => Promise<boolean> }) {
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);
  const have = recipe.score_details?.matched_ingredients?.length || 0;
  const missing = recipe.score_details?.missing_ingredients?.length || 0;
  return <article className="ai-title-card" style={{ "--card-index": index } as CSSProperties}>
    <button className="ai-title-main" onClick={() => onOpen()} aria-label={`Open ${recipe.title}`}>
      <div className="ai-title-copy"><span>AI idea {index + 1} · {recipeTotalMinutes(recipe)} min</span><h3>{recipe.title}</h3></div>
    </button>
    <footer>
      <span className="ai-title-stock"><b>{have}</b> in pantry{missing > 0 ? <> · <b>{missing}</b> to buy</> : " · nothing to buy"}</span>
      <div>
        <button className="ai-title-action" onClick={() => onOpen({ swaps: true })}><Icon name="swap" /> Swaps</button>
        {missing > 0 && <button className="ai-title-action primary" disabled={adding || added} onClick={async () => { setAdding(true); try { if (await onAddMissing()) setAdded(true); } finally { setAdding(false); } }}>{added ? <><Icon name="check" /> Added</> : adding ? "Adding…" : <>🛒 Add {missing} to list</>}</button>}
      </div>
    </footer>
  </article>;
}
