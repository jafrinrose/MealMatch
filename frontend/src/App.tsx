import { lazy, Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { api, errorMessage } from "./api";
import { pantryHasIngredient, recipeIngredientNames } from "./recipeFilters";
import "./recipe-cards.css";
import type { Tab, User, PantryItem, ShoppingItem, HomeInsights, RecipeOpenOptions, AiIdeas, ModelFeature, Recipe, CookingSession, UserPreferences } from "./types";
import { parseQuantity, expiryStatus } from "./utils";
import { readStorage, useStoredState, writeStorage } from "./storage";
import { DesktopSidebar, MobileNav, BrandMark, Icon } from "./components/ui";
import { IngredientSheet } from "./components/IngredientSheet";
import { HomeScreen } from "./screens/HomeScreen";
import { PantryScreen } from "./screens/PantryScreen";
import { RecipesScreen } from "./screens/RecipesScreen";
import { RecipeDetail } from "./screens/RecipeDetail";
import { ChatScreen } from "./screens/ChatScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { CookingMode } from "./screens/CookingMode";

// The opening film (with GSAP) and the tour load only when they are shown, so the app itself starts smaller.
const FridgeIntro = lazy(() => import("./components/FridgeIntro"));
const ExperienceWalkthrough = lazy(() => import("./components/ExperienceWalkthrough"));

const emptyPreferences: UserPreferences = {
  user_id: 1,
  dietary_restrictions: [],
  allergies: [],
  disliked_ingredients: [],
  preferred_cuisines: [],
  max_cooking_time: null,
  skill_level: "beginner",
  onboarding_complete: false,
};

const emptyHomeInsights: HomeInsights = {
  meals_cooked: 0,
  meals_this_week: 0,
  last_meal: null,
  top_ingredient: null,
  ingredients_used: 0,
  rescued_items: 0,
  rescue_rate: 0,
  estimated_savings: 0,
  last_rescue_count: 0,
  last_estimated_savings: 0,
};

function App() {
  const userId = 1;
  // The fridge film is the landing page once per browser session; "Replay the opening" on
  // the home screen shows it again. ?skipIntro=1 skips it and ?intro=1 forces it.
  const [introState, setIntroState] = useState<"playing" | "leaving" | "done">(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("intro") === "1") return "playing";
    if (params.get("skipIntro") === "1") return "done";
    return readStorage("mealmatch-intro-seen", "session") === "1" ? "done" : "playing";
  });
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    const requested = new URLSearchParams(window.location.search).get("tab");
    return (["home", "pantry", "recipes", "chat", "settings"] as Tab[]).includes(requested as Tab) ? requested as Tab : "home";
  });
  const [user, setUser] = useState<User>({ id: userId, name: "Home cook" });
  const [pantryItems, setPantryItems] = useState<PantryItem[]>([]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [recommendations, setRecommendations] = useState<Recipe[]>([]);
  const [recommendationsLoading, setRecommendationsLoading] = useState(true);
  const [preferences, setPreferences] = useState<UserPreferences>(emptyPreferences);
  const [shoppingList, setShoppingList] = useState<ShoppingItem[]>([]);
  const [homeInsights, setHomeInsights] = useState<HomeInsights>(emptyHomeInsights);
  const [loading, setLoading] = useState(true);
  const [selectedRecipe, setSelectedRecipe] = useState<Recipe | null>(null);
  const [detailOptions, setDetailOptions] = useState<RecipeOpenOptions>({});
  // Where the list was scrolled when a recipe (or cooking) opened, so Back returns there.
  const returnScroll = useRef<number | null>(null);
  const [activeCooking, setActiveCooking] = useState<CookingSession | null>(null);
  const [cookingView, setCookingView] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<PantryItem | null>(null);
  const [toast, setToast] = useState("");
  const toastTimer = useRef<number | null>(null);
  // AI features that cannot run (Ollama stopped, a model missing), from GET /health.
  const [modelIssues, setModelIssues] = useState<ModelFeature[]>([]);
  const [darkMode, setDarkMode] = useState(() => readStorage("mealmatch-theme") === "dark");
  // Set by "Use ingredients" on the home screen: the Recipes page then shows recipes that use these foods.
  const [recipeFocus, setRecipeFocus] = useState<string[] | null>(null);
  const [aiIdeas, setAiIdeas] = useStoredState<AiIdeas | null>("mealmatch-ai-ideas", null, "session");
  // "See how it works" plays by itself when the app is first loaded in a browser session,
  // after the opening film, whichever screen the app opens on (user testing, design iteration 4).
  const [tourOpen, setTourOpen] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("preview") === "experience") return true;
    if (params.get("skipTour") === "1") return false;
    return readStorage("mealmatch-tour-shown", "session") !== "1";
  });
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiError, setAiError] = useState("");

  // The pantry as saved now; the ranked suggestions follow it.
  async function reloadPantry() {
    const response = await api.get(`/pantry/${userId}`);
    const items: PantryItem[] = Array.isArray(response.data) ? response.data : [];
    setPantryItems(items);
    void loadRecommendations(items);
  }

  async function loadHomeInsights() {
    const response = await api.get(`/home-insights/${userId}`);
    setHomeInsights({ ...emptyHomeInsights, ...(response.data || {}) });
  }

  async function loadRecommendations(items: PantryItem[] = pantryItems) {
    if (items.length === 0) {
      setRecommendations([]);
      setRecommendationsLoading(false);
      return;
    }

    setRecommendationsLoading(true);
    try {
      const response = await api.get(`/recommend/${userId}`);
      setRecommendations(response.data.recommendations || []);
    } catch (error) {
      console.error("Could not load ranked recommendations", error);
      setRecommendations([]);
    } finally {
      setRecommendationsLoading(false);
    }
  }

  async function loadApp() {
    setLoading(true);
    try {
      const [usersResponse, pantryResponse, recipesResponse, preferencesResponse, cookingResponse, shoppingResponse, insightsResponse] = await Promise.all([
        api.get("/users"),
        api.get(`/pantry/${userId}`),
        api.get("/recipes", { params: { user_id: userId } }),
        api.get(`/preferences/${userId}`),
        api.get(`/cooking-session/${userId}`),
        api.get(`/shopping-list/${userId}`),
        api.get(`/home-insights/${userId}`).catch(() => ({ data: emptyHomeInsights })),
      ]);
      const loadedPantry = Array.isArray(pantryResponse.data) ? pantryResponse.data : [];
      setUser(usersResponse.data?.find((item: User) => item.id === userId) || { id: userId, name: "Home cook" });
      setPantryItems(loadedPantry);
      setRecipes(Array.isArray(recipesResponse.data) ? recipesResponse.data : []);
      setPreferences(preferencesResponse.data || emptyPreferences);
      setActiveCooking(cookingResponse.data || null);
      setShoppingList(Array.isArray(shoppingResponse.data) ? shoppingResponse.data : []);
      setHomeInsights({ ...emptyHomeInsights, ...(insightsResponse.data || {}) });
      void loadRecommendations(loadedPantry);
    } catch (error) {
      console.error("Could not load MealMatch", error);
      showToast("We couldn't reach the kitchen server. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadApp();
    // Checked in the background: the backend starts Ollama if needed, which can take a few seconds.
    api.get("/health")
      .then((response) => setModelIssues(((response.data?.features || []) as ModelFeature[]).filter((feature) => !feature.ready)))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = darkMode ? "dark" : "light";
    writeStorage("mealmatch-theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  function showToast(message: string) {
    // A new message gets its full time on screen: the previous message's timer no longer clears it early.
    if (toastTimer.current != null) window.clearTimeout(toastTimer.current);
    setToast(message);
    toastTimer.current = window.setTimeout(() => setToast(""), 3200);
  }

  // Runs something the cook asked for; if the server refuses or cannot be reached, says so instead of failing silently.
  async function attempt(action: () => Promise<void>, failure: string) {
    try {
      await action();
      return true;
    } catch (error) {
      console.error(failure, error);
      showToast(errorMessage(error, failure));
      return false;
    }
  }

  function enterKitchen() {
    writeStorage("mealmatch-intro-seen", "1", "session");
    setCookingView(false);
    setSelectedRecipe(null);
    setActiveTab("home");
    setIntroState("leaving");
  }

  function closeTour(goHome = false) {
    setTourOpen(false);
    writeStorage("mealmatch-tour-shown", "1", "session");
    const url = new URL(window.location.href);
    url.searchParams.delete("preview");
    window.history.replaceState(null, "", url);
    if (goHome) navigate("home");
  }

  function replayIntro() {
    window.scrollTo({ top: 0, behavior: "instant" });
    setIntroState("playing");
  }

  function navigate(tab: Tab) {
    returnScroll.current = null;
    setCookingView(false);
    setSelectedRecipe(null);
    setRecipeFocus(null);
    setActiveTab(tab);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // A recipe or the cooking view covers the current screen, which stays mounted
  // underneath (its search, filters and AI ideas survive), so remember its scroll.
  function rememberScroll() {
    if (!selectedRecipe && !cookingView) returnScroll.current = window.scrollY;
  }

  async function openRecipe(recipe: Recipe, options: RecipeOpenOptions = {}) {
    rememberScroll();
    setDetailOptions(options);
    try {
      const response = await api.get(`/recipes/${recipe.id}`, { params: { user_id: userId } });
      setSelectedRecipe({ ...recipe, ...response.data });
    } catch {
      setSelectedRecipe(recipe);
    }
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function showCooking() {
    rememberScroll();
    setCookingView(true);
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  // Back from a recipe or the cooking view: the screen underneath returns where the cook left it.
  useLayoutEffect(() => {
    if (selectedRecipe || cookingView || returnScroll.current === null) return;
    const top = returnScroll.current;
    returnScroll.current = null;
    window.scrollTo({ top, behavior: "instant" });
  }, [selectedRecipe, cookingView]);

  function addRecipeMissingToList(recipe: Recipe, servings = 1) {
    return attempt(async () => {
      const response = await api.post(`/shopping-list/${userId}/recipe/${recipe.id}`, { servings });
      setShoppingList(response.data.shopping_list || []);
      showToast(response.data.message);
    }, "Could not add the missing ingredients to your shopping list. Please try again.");
  }

  async function toggleSavedRecipe(recipe: Recipe) {
    const shouldSave = !recipe.saved;
    await attempt(async () => {
      if (shouldSave) await api.post(`/saved-recipes/${userId}/${recipe.id}`);
      else await api.delete(`/saved-recipes/${userId}/${recipe.id}`);
      const updateRecipe = (item: Recipe) => item.id === recipe.id ? { ...item, saved: shouldSave } : item;
      setRecipes((current) => current.map(updateRecipe));
      setRecommendations((current) => current.map(updateRecipe));
      setSelectedRecipe((current) => current?.id === recipe.id ? { ...current, saved: shouldSave } : current);
      showToast(shouldSave ? "Recipe saved for later." : "Recipe removed from saved recipes.");
    }, "Could not update your saved recipes. Please try again.");
  }

  async function removePantryItem(id: number) {
    await attempt(async () => {
      await api.delete(`/pantry/item/${id}`);
      await reloadPantry();
      showToast("Ingredient removed from your pantry.");
    }, "Could not remove that ingredient. Please try again.");
  }

  // "Meal is ready" takes what the meal used out of the pantry; show the new amounts at once.
  async function afterMealReady(message: string) {
    await reloadPantry();
    showToast(message);
    await loadHomeInsights();
  }

  function showUseSoonRecipes(ingredients: string[]) {
    navigate("recipes");
    setRecipeFocus(ingredients);
  }

  async function refreshAfterPantryChange(message: string) {
    setAddOpen(false);
    setEditingItem(null);
    await attempt(async () => {
      await reloadPantry();
      showToast(message);
    }, `${message} Reload the page to see it in your pantry.`);
  }

  async function toggleShopping(itemId: number) {
    try {
      const response = await api.put(`/shopping-list/item/${itemId}/toggle`);
      const fresh = response.data.shopping_list ?? (await api.get(`/shopping-list/${userId}`)).data;
      if (response.data.group_completed) {
        // Let the last tick land and the finished list celebrate before it leaves.
        setShoppingList((current) => current.map((item) => item.id === itemId ? { ...item, checked: true } : item));
        showToast(fresh.length ? "All picked up — that meal’s list is done and cleared." : "Everything’s picked up — your shopping list is clear.");
        window.setTimeout(() => setShoppingList(fresh), 1100);
      } else {
        setShoppingList(fresh);
      }
    } catch { showToast("Could not update your shopping list. Please try again."); }
  }

  async function clearShoppingList() {
    await attempt(async () => {
      await api.delete(`/shopping-list/${userId}`);
      setShoppingList([]);
      showToast("Shopping list deleted.");
    }, "Could not delete your shopping list. Please try again.");
  }

  // Three distinct ideas, shown one by one as each is ready. The variation is sent
  // separately so it never changes which pantry foods count as relevant.
  async function generateRecipeChoices(request: string, onProgress?: (recipes: Recipe[]) => void) {
    const variations = [
      "Offer the classic version of the requested dish.",
      "Offer a quicker, weeknight variation of the requested dish.",
      "Offer a different but coherent take on the request, in its own style.",
    ];
    const generated: Recipe[] = [];
    for (const variation of variations) {
      try {
        const response = await api.post(`/ai-recipes/${userId}`, { request, variation, avoid_titles: generated.map((recipe) => recipe.title) });
        const recipe: Recipe = response.data;
        if (generated.some((item) => item.id === recipe.id)) continue;
        generated.push(recipe);
        setRecipes((current) => [recipe, ...current.filter((item) => item.id !== recipe.id)]);
        onProgress?.([...generated]);
      } catch (error) {
        // One idea that fails its checks does not stop the next; only no ideas at all is an error.
        if (!generated.length && variation === variations[variations.length - 1]) throw error;
      }
    }
    return generated;
  }

  // The Recipes page's AI ideas live here, not in the page: they stay while the cook
  // opens one, switches tabs or reloads, until a new request or "Clear ideas"
  // (user testing, design iteration 3).
  async function createAiIdeas(request: string) {
    if (aiGenerating) return;
    setAiGenerating(true);
    setAiError("");
    setAiIdeas({ request, ids: [] });
    try {
      const options = await generateRecipeChoices(request, (progress) => setAiIdeas({ request, ids: progress.map((recipe) => recipe.id) }));
      setAiIdeas({ request, ids: options.map((recipe) => recipe.id) });
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setAiError(detail || "The AI recipe could not be created. Check that Ollama and llama3.2 are running.");
      setAiIdeas(null);
    } finally {
      setAiGenerating(false);
    }
  }

  const displayRecipes = useMemo(() => {
    const pantryNames = pantryItems.filter((item) => !expiryStatus(item.expiry_date).expired && parseQuantity(item.quantity).amount > 0).map((item) => item.ingredient);
    const recommendedIds = new Set(recommendations.map((recipe) => recipe.id));
    const base = recommendations.length > 0
      ? [...recommendations, ...recipes.filter((recipe) => !recommendedIds.has(recipe.id))]
      : recipes;
    const unique = Array.from(new Map(base.map((recipe) => [recipe.id, recipe])).values());
    const dietFirst = [...unique.filter((recipe) => !recipe.diet_conflicts?.length), ...unique.filter((recipe) => recipe.diet_conflicts?.length)];
    return dietFirst.map((recipe) => {
      const ingredients = recipeIngredientNames(recipe);
      const matched = ingredients.filter((ingredient) => pantryHasIngredient(ingredient, pantryNames));
      return {
        ...recipe,
        score_details: {
          final_score: ingredients.length ? matched.length / ingredients.length : 0,
          preference_score: 0.5,
          dietary_score: 1,
          cooking_time_score: recipe.cooking_time <= 30 ? 1 : 0.5,
          variety_score: 0.8,
          ...recipe.score_details,
          matched_ingredients: matched,
          missing_ingredients: ingredients.filter((ingredient) => !matched.includes(ingredient)),
          ingredient_match_score: ingredients.length ? matched.length / ingredients.length : 0,
        },
      };
    });
  }, [pantryItems, recipes, recommendations]);

  // While the film plays the app stays mounted (so its state survives a replay) but hidden,
  // and the film owns the page scroll.
  const hiddenForIntro = introState === "playing" ? { display: "none" } : undefined;
  // The fallback is the film's own dark first frame, so there is no white flash while it loads.
  const intro = introState !== "done" && <Suspense fallback={<div className="intro-loading" aria-hidden="true" />}>
    <FridgeIntro leaving={introState === "leaving"} onEnter={enterKitchen} onGone={() => setIntroState("done")} />
  </Suspense>;

  if (loading) {
    return (
      <>
        <div className="loading-screen" style={hiddenForIntro} role="status">
          <BrandMark />
          <p>MealMatch is loading<span className="loading-dots"><i /><i /><i /></span></p>
        </div>
        {intro}
      </>
    );
  }

  return (
    <>
    <div className="app-frame" style={hiddenForIntro}>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <DesktopSidebar activeTab={activeTab} onNavigate={navigate} />
      <main className="app-content" id="main-content" tabIndex={-1}>
        {modelIssues.length > 0 && (
          <aside className="model-notice" role="status">
            <Icon name="alert" />
            <div>
              <strong>Some AI features are not ready</strong>
              <ul>{modelIssues.map((issue) => <li key={issue.feature}><b>{issue.feature}</b> ({issue.model}): {issue.fix}</li>)}</ul>
            </div>
            <button onClick={() => setModelIssues([])} aria-label="Dismiss this notice"><Icon name="close" /></button>
          </aside>
        )}
        {cookingView && activeCooking && (
          <CookingMode
            session={activeCooking}
            onBack={() => setCookingView(false)}
            onSessionUpdate={setActiveCooking}
            onCancel={() => attempt(async () => {
              const response = await api.post(`/cooking-session/${userId}/cancel`);
              setActiveCooking(null);
              setCookingView(false);
              await reloadPantry();
              showToast(response.data.message);
            }, "Could not stop cooking. Please try again.").then(() => undefined)}
            onComplete={() => attempt(async () => {
              const response = await api.post(`/cooking-session/${userId}/complete`);
              setActiveCooking(null);
              setCookingView(false);
              setSelectedRecipe(null);
              await afterMealReady(response.data.message);
            }, "Could not finish the meal. Please try again.").then(() => undefined)}
          />
        )}
        {selectedRecipe && !(cookingView && activeCooking) && (
          <RecipeDetail
            key={selectedRecipe.id}
            recipe={selectedRecipe}
            pantryItems={pantryItems}
            userId={userId}
            openSwaps={Boolean(detailOptions.swaps)}
            onBack={() => setSelectedRecipe(null)}
            onToggleSaved={() => void toggleSavedRecipe(selectedRecipe)}
            onAddMissing={(servings) => addRecipeMissingToList(selectedRecipe, servings)}
            onCook={async (servings) => {
              if (activeCooking) {
                setCookingView(true);
                window.scrollTo({ top: 0, behavior: "instant" });
                showToast(`Resume ${activeCooking.recipe.title} before starting another recipe.`);
                return;
              }
              await attempt(async () => {
                const response = await api.post(`/recipes/${selectedRecipe.id}/cook/${userId}`, { servings });
                setActiveCooking(response.data.cooking_session);
                setCookingView(true);
                window.scrollTo({ top: 0, behavior: "instant" });
                showToast(response.data.message);
              }, "Could not start cooking. Please try again.");
            }}
          />
        )}
        <div className="tab-view" hidden={Boolean(selectedRecipe || (cookingView && activeCooking))}>
            {activeTab === "home" && (
              <HomeScreen
                name={user.name}
                pantryItems={pantryItems}
                recipes={displayRecipes}
                onAdd={() => setAddOpen(true)}
                onOpenRecipe={openRecipe}
                onNavigate={navigate}
                activeCooking={activeCooking}
                onResumeCooking={showCooking}
                onToggleSaved={(recipe) => void toggleSavedRecipe(recipe)}
                homeInsights={homeInsights}
                suggestionsLoading={recommendationsLoading}
                onUseSoon={showUseSoonRecipes}
                onReplayIntro={replayIntro}
                onShowTour={() => setTourOpen(true)}
              />
            )}
            {activeTab === "pantry" && (
              <PantryScreen
                items={pantryItems}
                onAdd={() => setAddOpen(true)}
                onEdit={setEditingItem}
                onRemove={(id) => void removePantryItem(id)}
                recipes={displayRecipes}
                shoppingList={shoppingList}
                onToggleShopping={toggleShopping}
                onClearList={clearShoppingList}
                onRemoveList={(recipeId) => attempt(async () => {
                  const response = await api.delete(`/shopping-list/${userId}/recipe/${recipeId ?? 0}`);
                  setShoppingList(response.data.shopping_list ?? shoppingList.filter((item) => item.recipe_id !== recipeId));
                  showToast("Meal shopping list removed.");
                }, "Could not delete that list. Please try again.").then(() => undefined)}
                onRemoveShopping={(itemId) => attempt(async () => {
                  await api.delete(`/shopping-list/item/${itemId}`);
                  setShoppingList((current) => current.filter((item) => item.id !== itemId));
                  showToast("Removed from your shopping list.");
                }, "Could not remove that item. Please try again.").then(() => undefined)}
              />
            )}
            {activeTab === "recipes" && (
              <RecipesScreen
                recipes={displayRecipes}
                preferences={preferences}
                onOpenRecipe={openRecipe}
                onToggleSaved={(recipe) => void toggleSavedRecipe(recipe)}
                aiIdeas={aiIdeas}
                aiGenerating={aiGenerating}
                aiError={aiError}
                onGenerate={createAiIdeas}
                onClearIdeas={() => { setAiIdeas(null); setAiError(""); }}
                onAddMissing={(recipe) => addRecipeMissingToList(recipe)}
                focusIngredients={recipeFocus}
                onClearFocus={() => setRecipeFocus(null)}
              />
            )}
            {activeTab === "chat" && (
              <ChatScreen
                userId={userId}
                recipes={displayRecipes}
                activeCooking={activeCooking}
                onSessionUpdate={setActiveCooking}
                onResumeCooking={showCooking}
                onCreateRecipes={generateRecipeChoices}
                onOpenRecipe={openRecipe}
                onToggleSaved={(recipe) => void toggleSavedRecipe(recipe)}
                onEndCooking={() => attempt(async () => {
                  const response = await api.post(`/cooking-session/${userId}/complete`);
                  setActiveCooking(null);
                  await afterMealReady(response.data.message);
                }, "Could not finish the meal. Please try again.").then(() => undefined)}
              />
            )}
            {activeTab === "settings" && (
              <SettingsScreen
                preferences={preferences}
                darkMode={darkMode}
                onThemeChange={setDarkMode}
                onSave={(updated) => attempt(async () => {
                  await api.put(`/preferences/${userId}`, { ...updated, onboarding_complete: true });
                  setPreferences({ ...preferences, ...updated, onboarding_complete: true });
                  const recipesResponse = await api.get("/recipes", { params: { user_id: userId } });
                  setRecipes(Array.isArray(recipesResponse.data) ? recipesResponse.data : []);
                  await loadRecommendations(pantryItems);
                  showToast("Your cooking preferences are saved.");
                }, "Could not save your preferences. Please try again.").then(() => undefined)}
              />
            )}
        </div>
      </main>
      {!selectedRecipe && !cookingView && <MobileNav activeTab={activeTab} onNavigate={navigate} />}
      {(addOpen || editingItem) && (
        <IngredientSheet
          userId={userId}
          editingItem={editingItem}
          onClose={() => {
            setAddOpen(false);
            setEditingItem(null);
          }}
          onSaved={(message) => void refreshAfterPantryChange(message)}
        />
      )}
      {toast && <div className="toast" role="status" aria-live="polite"><Icon name="check" />{toast}</div>}
    </div>
    {intro}
    {/* The tour locks page scrolling, so it waits until the opening film and the first load have finished. */}
    {tourOpen && introState === "done" && <Suspense fallback={null}><ExperienceWalkthrough onFinish={() => closeTour()} onTryIt={() => closeTour(true)} /></Suspense>}
    </>
  );
}

export default App;
