import { useEffect, useState } from "react";
import { api } from "../api";
import { pantryHasIngredient, recipeTotalMinutes } from "../recipeFilters";
import type { PantryItem, IngredientDetail, Substitution, Recipe } from "../types";
import { splitIngredients, titleCase, parseQuantity, formatAmount, fallbackStepMinutes, recipeDescription, expiryStatus } from "../utils";
import { Icon } from "../components/ui";
import { IngredientEmoji, RecipeArtwork } from "../components/FoodArt";

const ingredientAmounts: Record<string, IngredientDetail> = {
  chicken: { name: "chicken", amount: 180, unit: "g" },
  rice: { name: "rice", amount: 1, unit: "cup" },
  spinach: { name: "spinach", amount: 2, unit: "cups" },
  "soy sauce": { name: "soy sauce", amount: 1, unit: "tbsp" },
  garlic: { name: "garlic", amount: 2, unit: "cloves" },
  pasta: { name: "pasta", amount: 180, unit: "g" },
  tomato: { name: "tomato", amount: 2, unit: "pieces" },
  cheese: { name: "cheese", amount: 0.5, unit: "cup" },
  egg: { name: "egg", amount: 2, unit: "pieces" },
  milk: { name: "milk", amount: 1, unit: "cup" },
};

export function RecipeDetail({ recipe, pantryItems, userId, openSwaps = false, onBack, onCook, onToggleSaved, onAddMissing }: { recipe: Recipe; pantryItems: PantryItem[]; userId: number; openSwaps?: boolean; onBack: () => void; onCook: (servings: number) => Promise<void>; onToggleSaved: () => void; onAddMissing: (servings: number) => Promise<boolean>; }) {
  const [servings, setServings] = useState(1);
  const [cooking, setCooking] = useState(false);
  // Swaps per ingredient, fetched when the cook taps Swap on it: suggestions, or "error".
  const [swaps, setSwaps] = useState<Record<string, Substitution["suggestions"] | "error">>({});
  const [findingSwap, setFindingSwap] = useState<string | null>(null);
  const [expandedSubstitution, setExpandedSubstitution] = useState<string | null>(null);
  const [addingShopping, setAddingShopping] = useState(false);
  const pantryNames = pantryItems.filter((item) => !expiryStatus(item.expiry_date).expired && parseQuantity(item.quantity).amount > 0).map((item) => item.ingredient);
  const details = recipe.ingredient_details || splitIngredients(recipe.ingredients).map((name) => ingredientAmounts[name] || { name, amount: 1, unit: "portion" });
  const steps = recipe.step_details || (recipe.instruction_steps || recipe.instructions.split(/(?<=[.!?])\s+/).filter(Boolean)).map((instruction, index, all) => ({ instruction, minutes: fallbackStepMinutes(instruction, index, all.length, recipe) }));
  const missingDetails = details.filter((item) => !pantryHasIngredient(item.name, pantryNames));

  async function startCooking() {
    setCooking(true);
    try { await onCook(servings); } finally { setCooking(false); }
  }

  async function findSwaps(ingredient: string) {
    setFindingSwap(ingredient);
    try {
      const response = await api.get(`/recipes/${recipe.id}/substitutes/${userId}`, { params: { ingredient } });
      const group = (response.data.substitutions as Substitution[] | undefined)?.[0];
      setSwaps((current) => ({ ...current, [ingredient]: group?.suggestions || [] }));
    } catch {
      setSwaps((current) => ({ ...current, [ingredient]: "error" }));
    } finally {
      setFindingSwap((current) => current === ingredient ? null : current);
    }
  }

  useEffect(() => {
    if (!openSwaps) return;
    // Opened from "Swaps" on an AI idea: show alternatives for what is missing first.
    const first = missingDetails[0]?.name || details[0]?.name;
    if (!first) return;
    setExpandedSubstitution(first);
    void findSwaps(first);
    window.setTimeout(() => document.querySelector(".ingredients-card")?.scrollIntoView({ behavior: "smooth", block: "start" }), 250);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once, when the recipe opens
  }, []);

  function toggleSubstitution(ingredient: string) {
    if (expandedSubstitution === ingredient) {
      setExpandedSubstitution(null);
      return;
    }
    setExpandedSubstitution(ingredient);
    if (swaps[ingredient] === undefined || swaps[ingredient] === "error") void findSwaps(ingredient);
  }

  async function addMissing() {
    setAddingShopping(true);
    try { await onAddMissing(servings); } finally { setAddingShopping(false); }
  }

  return (
    <article className="recipe-detail screen">
      <div className="detail-topbar"><button className="back-button" onClick={onBack}><Icon name="back" /> Back to recipes</button><button className={`detail-save ${recipe.saved ? "saved" : ""}`} onClick={onToggleSaved}><Icon name="bookmark" />{recipe.saved ? "Saved" : "Save recipe"}</button></div>
      <header className="detail-hero">
        <div className="detail-hero-copy"><p className="eyebrow">{recipe.cuisine} · {recipe.difficulty}</p><h1>{recipe.title}</h1><p>{recipeDescription(recipe)}</p><div className="detail-meta"><span><Icon name="clock" />Prep {recipe.prep_time ?? 10} min</span><span>Cook {recipe.cooking_time} min</span><span>Total {recipeTotalMinutes(recipe)} min</span>{recipe.calories > 0 && <span>🔥 {recipe.calories} kcal</span>}</div>{recipe.source && <small className="recipe-source">Recipe source: {recipe.source}</small>}</div>
        <div className={`detail-food ${recipe.image_url ? "with-photo" : ""}`} aria-hidden="true"><RecipeArtwork recipe={recipe} /></div>
      </header>
      <div className="cook-bar detail-primary-action"><div><strong>Ready to make it?</strong><span>Mimi will guide every step and update your pantry when the meal is ready.</span></div><button className="primary-button" disabled={cooking} onClick={() => void startCooking()}><Icon name="chef" />{cooking ? "Starting…" : "I’m cooking this"}</button></div>
      <div className="detail-layout">
        <section className="ingredients-card">
          <div className="gather-first-row"><p className="eyebrow">Gather first</p>{missingDetails.length > 0 && <button className="add-missing-text" disabled={addingShopping} onClick={() => void addMissing()}>{addingShopping ? "Adding…" : `Add ${missingDetails.length} missing to list`} <Icon name="arrow" /></button>}</div>
          <div className="detail-section-title"><h2>Ingredients</h2><div className="servings"><button aria-label="Fewer servings" onClick={() => setServings(Math.max(1, servings - 1))}>−</button><span>{servings} serving{servings > 1 ? "s" : ""}</span><button aria-label="More servings" onClick={() => setServings(Math.min(12, servings + 1))}>+</button></div></div>
          <div className="ingredient-detail-list">
            {details.map((item) => {
              const hasIt = pantryHasIngredient(item.name, pantryNames);
              const found = swaps[item.name];
              const finding = findingSwap === item.name;
              const expanded = expandedSubstitution === item.name;
              return <article className={`ingredient-detail-item ${hasIt ? "available" : "missing"}`} key={item.name}>
                <div className="ingredient-detail-row"><span className={hasIt ? "ingredient-check checked" : "ingredient-check"}>{hasIt && <Icon name="check" />}</span><IngredientEmoji name={item.name} small /><div className="ingredient-name"><strong>{titleCase(item.name)}</strong><small>{hasIt ? "In pantry" : "Missing"}</small></div><span className="ingredient-amount">{formatAmount(item.amount * servings)} {item.unit}</span><button className={expanded ? "ingredient-swap active" : "ingredient-swap"} onClick={() => toggleSubstitution(item.name)} aria-expanded={expanded} aria-label={`Find a substitute for ${item.name}`}><Icon name="swap" /><span>{finding ? "Finding" : "Swap"}</span></button></div>
                {expanded && <div className="inline-substitutions" aria-live="polite">{finding || found === undefined ? <p>Finding swaps that suit your pantry and diet…</p> : found === "error" ? <p>Swaps could not be loaded. <button className="swap-retry" onClick={() => void findSwaps(item.name)}>Try again</button></p> : found.length ? found.map((suggestion) => <div className={suggestion.in_pantry ? "inline-substitution pantry-pick" : "inline-substitution"} key={suggestion.name}><span><IngredientEmoji name={suggestion.name} small /></span><div><strong>{titleCase(suggestion.name)}</strong><p>{suggestion.reason}</p></div><em>{suggestion.in_pantry ? "In pantry" : "Alternative"}</em></div>) : <p>No safe swap was found for {item.name}. It may be easier to add it to your shopping list.</p>}</div>}
              </article>;
            })}
          </div>

        </section>
        <section className="steps-card">
          <p className="eyebrow">One step at a time</p><h2>Method</h2>
          <ol>{steps.map((step, index) => <li key={`${index}-${step.instruction}`}><span>{index + 1}</span><div><small>About {step.minutes} min</small><p>{step.instruction}</p></div></li>)}</ol>
        </section>
      </div>
    </article>
  );
}
