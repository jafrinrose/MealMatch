import type { Recipe } from "../types";
import { splitIngredients, titleCase, recipeDescription } from "../utils";
import { Icon } from "./ui";
import { RecipeArtwork } from "./FoodArt";

export function RecipeCard({ recipe, index, onClick, onToggleSaved, highlight }: { recipe: Recipe; index: number; onClick: () => void; onToggleSaved: () => void; highlight?: string[] }) {
  const ingredients = splitIngredients(recipe.ingredients);
  const matched = recipe.score_details?.matched_ingredients || [];
  const match = Math.round((recipe.score_details?.ingredient_match_score || 0) * 100);
  const missing = Math.max(ingredients.length - matched.length, 0);
  const palettes = ["peach", "mint", "lavender", "sunny"];
  // Food this recipe saves from the bin: the page's use-soon filter, or the ranking's own list.
  const rescues = highlight?.length ? highlight : recipe.score_details?.expiring_matched_ingredients || [];
  const dietConflict = recipe.diet_conflicts?.[0];

  return (
    <article className="recipe-card">
      <button className={`save-recipe ${recipe.saved ? "saved" : ""}`} onClick={onToggleSaved} aria-label={recipe.saved ? "Remove saved recipe" : "Save recipe"}><Icon name="bookmark" /></button>
      <button className="recipe-card-main" onClick={onClick}>
      <div className={`recipe-visual ${palettes[index % palettes.length]}`}>
        <RecipeArtwork recipe={recipe} lazy />
        {recipe.source === "MealMatch AI" && <span className="ai-choice-badge"><Icon name="sparkles" /> AI-created</span>}
        {rescues.length > 0 && !dietConflict && <span className="use-first-badge"><Icon name="alert" /> Uses {titleCase(rescues[0])}{rescues.length > 1 ? ` +${rescues.length - 1}` : ""} before it expires</span>}
        {dietConflict && <span className="diet-conflict-badge"><Icon name="alert" /> Not {dietConflict.diet} · {dietConflict.ingredients.join(", ")}</span>}
        {missing === 0 && matched.length > 0 && <span className="complete-badge"><Icon name="check" /> All ingredients</span>}
        <span className="view-recipe">View recipe <Icon name="arrow" /></span>
      </div>
      <div className="recipe-card-body">
        <h3>{recipe.title}</h3>
        <p>{recipeDescription(recipe)}</p>
        <div className="recipe-meta"><span><Icon name="clock" />Prep {recipe.prep_time ?? 10}m · Cook {recipe.cooking_time}m</span><span>{recipe.instruction_steps?.length || recipe.instructions.split(".").filter(Boolean).length} steps</span><span>{recipe.cuisine}</span>{recipe.calories > 0 && <span>{recipe.calories} kcal</span>}</div>
        <div className="recipe-match-block"><div className="match-label"><span>Pantry match</span><strong>{match}%</strong></div><div className="progress-track"><span style={{ width: `${match}%` }} /></div><div className="ingredient-count"><span className="have"><Icon name="check" />{matched.length} have</span>{missing > 0 && <span className="missing">× {missing} missing</span>}</div></div>
      </div>
      </button>
    </article>
  );
}
