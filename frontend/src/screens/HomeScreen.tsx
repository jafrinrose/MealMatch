import { useState } from "react";
import chefMascot from "../assets/chef-mascot.webp";
import type { Tab, PantryItem, HomeInsights, Recipe, CookingSession } from "../types";
import { pantryCategories, titleCase, greeting, categoryEmoji, normalizedCategory, expiryStatus } from "../utils";
import { CountdownText, PageHeader, EmptyState, Icon } from "../components/ui";
import { IngredientEmoji } from "../components/FoodArt";
import { RecipeCard } from "../components/RecipeCard";

export function HomeScreen({
  name,
  pantryItems,
  recipes,
  onAdd,
  onOpenRecipe,
  onNavigate,
  activeCooking,
  onResumeCooking,
  onToggleSaved,
  homeInsights,
  suggestionsLoading,
  onUseSoon,
  onReplayIntro,
  onShowTour,
}: {
  name: string;
  pantryItems: PantryItem[];
  recipes: Recipe[];
  onAdd: () => void;
  onOpenRecipe: (recipe: Recipe) => void;
  onNavigate: (tab: Tab) => void;
  activeCooking: CookingSession | null;
  onResumeCooking: () => void;
  onToggleSaved: (recipe: Recipe) => void;
  homeInsights: HomeInsights;
  suggestionsLoading: boolean;
  onUseSoon: (ingredients: string[]) => void;
  onReplayIntro: () => void;
  onShowTour: () => void;
}) {
  const [hoveredPantryCategory, setHoveredPantryCategory] = useState<string | null>(null);
  // Food to use soon: not yet expired, soonest first. Expired food is counted in the insights, not offered for cooking.
  const useSoonItems = pantryItems
    .filter((item) => { const status = expiryStatus(item.expiry_date); return status.urgent && !status.expired; })
    .sort((first, second) => first.expiry_date.localeCompare(second.expiry_date));
  const expiringItems = useSoonItems.slice(0, 4);
  // "Find recipes" looks for the foods the panel shows: the most urgent ones.
  const useSoonNames = expiringItems.map((item) => item.ingredient);
  const firstName = name.split(" ")[0];
  const freshness = pantryItems.reduce((counts, item) => {
    const status = expiryStatus(item.expiry_date);
    if (status.label === "Expired") counts.expired += 1;
    else if (status.urgent) counts.expiring += 1;
    else counts.fresh += 1;
    return counts;
  }, { fresh: 0, expiring: 0, expired: 0 });
  const rawCategoryCounts = pantryCategories.slice(1).map((category) => ({ category, label: titleCase(category), count: pantryItems.filter((item) => normalizedCategory(item.category, item.ingredient) === category).length })).filter((item) => item.count > 0).sort((first, second) => second.count - first.count);
  const categoryColors = ["#e83f8f", "#24b9a3", "#9b7df3", "#f5b724", "#42afe3", "#ff7188"];
  const pantryCategorySummary = rawCategoryCounts.length > 6 ? [...rawCategoryCounts.slice(0, 5), { category: "more", label: "More", count: rawCategoryCounts.slice(5).reduce((total, item) => total + item.count, 0) }] : rawCategoryCounts;
  let donutCursor = 0;
  const pantryCategorySegments = pantryCategorySummary.map((item, index) => {
    const percentage = pantryItems.length ? (item.count / pantryItems.length) * 100 : 0;
    const segment = { ...item, color: categoryColors[index % categoryColors.length], percentage, offset: donutCursor };
    donutCursor += percentage;
    return segment;
  });
  const hoveredSegment = pantryCategorySegments.find((item) => item.category === hoveredPantryCategory) || null;

  return (
    <div className="screen home-screen">
      <PageHeader
        eyebrow={greeting()}
        title={`${firstName} 👋`}
        action={<button className="icon-button add-main" onClick={onAdd} aria-label="Add ingredient"><Icon name="plus" /></button>}
      />

      {activeCooking && (
        <button className="active-cooking-banner" onClick={onResumeCooking}>
          <span className="cooking-pulse"><Icon name="chef" /></span>
          <div><small>Cooking now</small><strong>{activeCooking.recipe.title}</strong><span>Food ready in <CountdownText readyAt={activeCooking.ready_at} /></span></div>
          <span className="resume-label">Resume <Icon name="arrow" /></span>
        </button>
      )}

      <section className="home-hero">
        <div>
          <span className="hero-kicker">Tonight’s little win</span>
          <h2>Your fridge already has<br />the start of something good.</h2>
          <p>{pantryItems.length} pantry items are ready to become dinner.</p>
          <div className="hero-actions">
            <button className="light-button" onClick={() => onNavigate("recipes")}>Find my meal <Icon name="arrow" /></button>
            <button className="hero-preview-button" onClick={onShowTour}><Icon name="sparkles" /> See how it works</button>
            <button className="hero-preview-button replay-opening-button" onClick={onReplayIntro}><Icon name="play" /> Replay the opening</button>
          </div>
        </div>
        <div className="chef-mascot" aria-hidden="true">
          <span className="chef-glow" />
          <img src={chefMascot} alt="" />
          <b className="chef-hat-badge">MM</b>
          <i className="chef-spark spark-one">✦</i>
          <i className="chef-spark spark-two">✦</i>
        </div>
      </section>

      <section className="pantry-insights">
        <header><div><span className="section-icon"><Icon name="pantry" /></span><div><p className="eyebrow">Inventory at a glance</p><h2>Pantry insights</h2></div></div><button onClick={() => onNavigate("pantry")}>{pantryItems.length} item{pantryItems.length === 1 ? "" : "s"} <Icon name="arrow" /></button></header>
        <div className="freshness-stats">
          <div className="fresh"><strong>{freshness.fresh}</strong><span>Fresh</span></div>
          <div className="expiring"><strong>{freshness.expiring}</strong><span>Expiring soon</span></div>
          <div className="expired"><strong>{freshness.expired}</strong><span>Expired</span></div>
        </div>
        <div className="freshness-track" aria-label={`${freshness.fresh} fresh, ${freshness.expiring} expiring soon and ${freshness.expired} expired items`}><span className="expired" style={{ width: `${pantryItems.length ? (freshness.expired / pantryItems.length) * 100 : 0}%` }} /><span className="expiring" style={{ width: `${pantryItems.length ? (freshness.expiring / pantryItems.length) * 100 : 0}%` }} /><span className="fresh" style={{ width: `${pantryItems.length ? (freshness.fresh / pantryItems.length) * 100 : 0}%` }} /></div>
        <div className="freshness-legend"><span className="expired"><i />Expired ({freshness.expired})</span><span className="expiring"><i />Expiring ({freshness.expiring})</span><span className="fresh"><i />Fresh ({freshness.fresh})</span></div>
        <div className="pantry-category-breakdown">
          <div className="pantry-donut" onMouseLeave={() => setHoveredPantryCategory(null)}>
            <svg viewBox="0 0 120 120" role="img" aria-label={`Category distribution for ${pantryItems.length} pantry items`}>
              <circle className="donut-base" cx="60" cy="60" r="44" pathLength="100" />
              {pantryCategorySegments.map((item) => <circle className={hoveredPantryCategory === item.category ? "donut-segment active" : "donut-segment"} key={`${item.category}-${item.label}`} cx="60" cy="60" r="44" pathLength="100" stroke={item.color} strokeDasharray={`${item.percentage} ${100 - item.percentage}`} strokeDashoffset={-item.offset} tabIndex={0} role="button" aria-label={`${item.label}, ${item.count} items`} onMouseEnter={() => setHoveredPantryCategory(item.category)} onFocus={() => setHoveredPantryCategory(item.category)} onBlur={() => setHoveredPantryCategory(null)} onClick={() => setHoveredPantryCategory((current) => current === item.category ? null : item.category)} />)}
            </svg>
            <span className="donut-total"><strong>{pantryItems.length}</strong><small>items</small></span>
            {hoveredSegment && <div className="donut-tooltip"><b>{hoveredSegment.category === "more" ? "🧺" : categoryEmoji(hoveredSegment.category)} {hoveredSegment.label}</b><span>· {hoveredSegment.count} item{hoveredSegment.count === 1 ? "" : "s"}</span></div>}
          </div>
          <div className="pantry-category-legend">{pantryCategorySegments.map((item) => <button aria-label={`Show ${item.label}: ${item.count} items`} className={hoveredPantryCategory === item.category ? "active" : ""} key={`${item.category}-${item.label}`} onMouseEnter={() => setHoveredPantryCategory(item.category)} onMouseLeave={() => setHoveredPantryCategory(null)} onFocus={() => setHoveredPantryCategory(item.category)} onBlur={() => setHoveredPantryCategory(null)} onClick={() => setHoveredPantryCategory((current) => current === item.category ? null : item.category)}><i style={{ background: item.color }} /><span>{item.category === "more" ? "🧺" : categoryEmoji(item.category)} {item.label}</span><strong>{item.count}</strong></button>)}</div>
        </div>
      </section>

      {expiringItems.length > 0 && (
        <section className="expiring-panel">
          <div className="section-heading compact-heading">
            <div><span className="section-icon alert"><Icon name="alert" /></span><h2>Use soon</h2></div>
            <button className="use-ingredients-link" onClick={() => onUseSoon(useSoonNames)}>Find recipes <Icon name="arrow" /></button>
          </div>
          <div className="expiry-row">
            {expiringItems.map((item) => {
              const status = expiryStatus(item.expiry_date);
              return <div className="expiry-card" key={item.id}><IngredientEmoji name={item.ingredient} /><div><strong>{titleCase(item.ingredient)}</strong><span>{item.quantity || "Quantity not set"}</span><small>{status.label}{item.expiry_estimated ? " · estimated" : ""}</small></div></div>;
            })}
          </div>
        </section>
      )}

      <ImpactPanel insights={homeInsights} canRescue={useSoonNames.length > 0} onRescue={() => onUseSoon(useSoonNames)} />

      <section className="recipe-section">
        <div className="section-heading">
          <div><span className="section-icon"><Icon name="chef" /></span><div><p className="eyebrow">Made for your pantry</p><h2>Suggested for you</h2></div></div>
          <button onClick={() => onNavigate("recipes")}>See all <Icon name="arrow" /></button>
        </div>
        <div className="recipe-grid home-recipes">
          {suggestionsLoading
            ? Array.from({ length: 4 }, (_, index) => <div className="recipe-card is-skeleton" key={`suggestion-${index}`} aria-hidden="true"><div /><span /><span /></div>)
            : recipes.slice(0, 4).map((recipe, index) => <RecipeCard key={recipe.id} recipe={recipe} index={index} onClick={() => onOpenRecipe(recipe)} onToggleSaved={() => onToggleSaved(recipe)} />)}
        </div>
        {!suggestionsLoading && recipes.length === 0 && <EmptyState icon="chef" title="Your menu is warming up" text="Add a few pantry items and we'll find recipes that fit." action="Add ingredients" onAction={onAdd} />}
      </section>
    </div>
  );
}

function ImpactPanel({ insights, canRescue, onRescue }: { insights: HomeInsights; canRescue: boolean; onRescue: () => void }) {
  const saved = insights.rescued_items;
  const grams = insights.estimated_grams_saved || 0;
  const weeks = insights.weekly_rescues || [];
  const peak = Math.max(1, ...weeks.map((week) => week.count));
  const windowDays = insights.rescue_window_days || 5;
  const atRisk = insights.at_risk_items || [];
  const events = insights.rescue_events || [];
  const weekLabel = (value: string) => new Date(`${value}T00:00:00`).toLocaleDateString([], { day: "numeric", month: "short" });
  return <section className="waste-impact-card impact-panel" aria-labelledby="impact-title">
    {insights.last_rescue_count > 0 && <div className="rescue-accomplishment"><span>✦</span><div><small>Latest kitchen win</small><strong>You saved {insights.last_rescue_count} ingredient{insights.last_rescue_count === 1 ? "" : "s"}</strong><p>In your last meal: <b>{insights.last_meal}</b></p></div></div>}
    <header><div><p className="eyebrow">Food kept out of the bin</p><h2 id="impact-title">Food waste impact</h2></div><span className="impact-leaf" aria-hidden="true">🌱</span></header>
    <div className="impact-hero">
      <div className="impact-big"><strong>{saved}</strong><span>ingredient{saved === 1 ? "" : "s"} saved</span><small>cooked within {windowDays} days of expiring</small></div>
      <div className="impact-stats">
        <div><strong>{grams >= 1000 ? `${(grams / 1000).toFixed(1)} kg` : `${grams} g`}</strong><span>food saved (est.)</span></div>
        <div><strong>{(insights.estimated_co2e_kg || 0).toFixed(1)} kg</strong><span>CO₂e avoided (est.)</span></div>
        <div><strong>{insights.meals_cooked}</strong><span>meal{insights.meals_cooked === 1 ? "" : "s"} cooked in MealMatch</span></div>
      </div>
    </div>
    {weeks.length > 0 && <div className="impact-trend" role="img" aria-label={`Ingredients saved per week for the last ${weeks.length} weeks: ${weeks.map((week) => week.count).join(", ")}`}>
      {weeks.map((week, index) => <div key={week.week_start} className={index === weeks.length - 1 ? "current" : ""}><b>{week.count || ""}</b><i style={{ height: `${Math.max(week.count ? 12 : 3, (week.count / peak) * 100)}%` }} /><span>{index === weeks.length - 1 ? "This week" : weekLabel(week.week_start)}</span></div>)}
    </div>}
    {events.length > 0 && <div className="impact-events">{events.slice(0, 3).map((event, index) => <div key={`${event.session_id}-${event.ingredient}-${index}`}><IngredientEmoji name={event.ingredient} small /><p><strong>{titleCase(event.ingredient)}</strong><small>{event.days_to_expiry === 0 ? "Saved on its last day" : `Saved ${event.days_to_expiry} day${event.days_to_expiry === 1 ? "" : "s"} before expiry`} · {event.recipe_title}</small></p>{event.estimated_grams ? <em>{event.estimated_grams} g</em> : null}</div>)}</div>}
    {atRisk.length > 0 && <div className="impact-at-risk"><span aria-hidden="true">⏳</span><div><strong>{insights.at_risk_count} item{insights.at_risk_count === 1 ? "" : "s"} could be saved this week</strong><small>{atRisk.slice(0, 4).map((item) => titleCase(item.ingredient)).join(", ")}{atRisk.length > 4 ? "…" : ""}</small></div><button disabled={!canRescue} onClick={onRescue}>Cook them <Icon name="arrow" /></button></div>}
    {saved === 0 && <p className="impact-empty">Cook something that uses your “Use soon” food and finish the meal in MealMatch. Every ingredient used before it expires is counted here.</p>}
    <small className="impact-note">Counted when you finish cooking: pantry foods used 0–{windowDays} days before their expiry date (some dates are estimated). Weight comes from recorded amounts or typical portions; CO₂e uses 2.5 kg per kg of food not wasted.</small>
  </section>;
}
