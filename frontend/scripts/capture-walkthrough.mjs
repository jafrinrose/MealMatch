// Captures the product-tour screens from the running app.
//
//   1. Start the backend (port 8000) and `npm run dev` (port 5173).
//   2. npm run capture:tour            (or: node scripts/capture-walkthrough.mjs http://localhost:5173)
//
// Screens are the real MealMatch UI. A handful of endpoints answer with the sample
// kitchen in walkthrough-fixtures.json (insights, shopping list, a photo scan, three
// AI ideas and a cooking session), so capturing never writes to your database and the
// tour looks the same for everyone. Output: public/walkthrough/*.jpg and
// src/components/walkthrough-steps.json (hotspot and camera positions, measured from the DOM).
import { chromium } from "playwright-core";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const BASE = process.argv[2] || "http://localhost:5173";
const here = (path) => fileURLToPath(new URL(path, import.meta.url));
const OUT = here("../public/walkthrough/");
const STEPS_FILE = here("../src/components/walkthrough-steps.json");
const fixtures = JSON.parse(readFileSync(here("./walkthrough-fixtures.json"), "utf8"));
const CHROME = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const VIEW = { width: 1440, height: 1000 };
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ executablePath: CHROME });
const context = await browser.newContext({ viewport: VIEW, deviceScaleFactor: 1.5 });
await context.addInitScript(() => { try { sessionStorage.setItem("mealmatch-tour-shown", "1"); } catch { /* ignore */ } });

// ---- Sample kitchen -------------------------------------------------------
const recipes = new Map(fixtures.recipes.map((recipe) => [recipe.id, recipe]));
let aiCall = 0;
let cooking = false;
const now = Date.now();
await context.route("**/api/home-insights/*", (route) => route.fulfill({ json: fixtures.insights }));
await context.route("**/api/shopping-list/*", (route) => route.request().method() === "GET" ? route.fulfill({ json: fixtures.shopping }) : route.fallback());
// The app reads photo results as a stream: one JSON line per model pass, then "done".
await context.route("**/api/upload-image", (route) => route.fulfill({
  contentType: "application/x-ndjson",
  body: `${JSON.stringify({ type: "suggestions", scan_id: fixtures.scan.scan_id, pass_number: 1, passes: 1, detections: fixtures.scan.detections, alternatives: [] })}\n${JSON.stringify({ type: "done", warnings: fixtures.scan.warnings || [] })}\n`,
}));
await context.route("**/api/vision/warmup", (route) => route.fulfill({ json: { status: "warming" } }));
await context.route("**/api/ai-recipes/*", async (route) => {
  await new Promise((resolve) => setTimeout(resolve, 400));
  const recipe = fixtures.recipes[aiCall++ % fixtures.recipes.length];
  route.fulfill({ json: { ...recipe, image_url: "" } });
});
await context.route(/\/api\/recipes\/9\d{3}(\/substitutes\/\d+)?(\?.*)?$/, (route) => {
  const url = new URL(route.request().url());
  const id = Number(url.pathname.match(/recipes\/(\d+)/)[1]);
  if (url.pathname.includes("/substitutes/")) {
    // The app asks for one ingredient at a time (the one tapped).
    const groups = fixtures.substitutions[id]?.substitutions || [];
    const wanted = url.searchParams.get("ingredient")?.toLowerCase();
    return route.fulfill({ json: { substitutions: wanted ? groups.filter((group) => group.ingredient === wanted) : groups } });
  }
  return route.fulfill({ json: recipes.get(id) });
});
await context.route("**/api/cooking-session/*", (route) => {
  if (!cooking || route.request().method() !== "GET") return route.fallback();
  const started = new Date(now - 6 * 60000).toISOString();
  const ready = new Date(now + 19 * 60000).toISOString();
  route.fulfill({ json: { ...fixtures.session, started_at: started, ready_at: ready, recipe: recipes.get(fixtures.session.recipe_id) } });
});

// ---- Helpers -----------------------------------------------------------------
const page = await context.newPage();
const steps = {};
async function open(query) {
  await page.goto(`${BASE}/?skipIntro=1&${query}#app`);
  await page.waitForSelector(".app-frame", { timeout: 30000 });
  await page.waitForTimeout(1200);
}
async function center(selector) {
  const box = await page.locator(selector).first().boundingBox();
  if (!box) throw new Error(`Nothing on screen for ${selector}`);
  return { x: +((box.x + box.width / 2) / VIEW.width).toFixed(4), y: +((box.y + box.height / 2) / VIEW.height).toFixed(4) };
}
async function capture(id, hotspot, focus, scale = 1.14) {
  await page.locator(focus).first().scrollIntoViewIfNeeded();
  await page.evaluate(() => document.querySelectorAll("img").forEach((image) => image.loading = "eager"));
  await page.waitForTimeout(900);
  const spot = await center(hotspot);
  const zoom = await center(focus);
  await page.screenshot({ path: `${OUT}${id}.jpg`, type: "jpeg", quality: 82 });
  steps[id] = { image: `/walkthrough/${id}.jpg`, x: spot.x, y: spot.y, zoom: { x: zoom.x, y: zoom.y, scale } };
  console.log("captured", id);
}

// ---- The tour ------------------------------------------------------------------
await open("tab=home");
await page.waitForSelector(".home-recipes .recipe-card:not(.is-skeleton)", { timeout: 30000 });
await capture("home", ".hero-actions .light-button", ".home-hero", 1.08);

await page.click(".add-main");
await page.click(".mode-tabs button:has-text('Photo')");
await capture("add", ".scan-panel .primary-button", ".ingredient-sheet", 1.08);

await page.setInputFiles(".scan-panel input[type=file]", here("../public/tutorial-fridge.png"));
await page.waitForSelector(".detected-list", { timeout: 20000 });
await capture("confirm", ".scan-panel .sheet-save", ".detected-list", 1.08);

await open("tab=pantry");
await capture("pantry", ".pantry-item span.urgent", ".pantry-list", 1.12);

await open("tab=recipes");
await page.fill("input[aria-label='Search recipes']", "pasta");
await page.waitForTimeout(600);
await capture("recipes", ".search-field input", ".recipe-grid", 1.08);

await page.fill("input[aria-label='Search recipes']", "");
await page.click(".ai-recipe-button");
await page.fill("input[aria-label='Describe the recipes you want']", fixtures.request);
await page.click("text=Show 3 ideas");
await page.waitForFunction(() => document.querySelectorAll(".ai-title-card:not(.is-skeleton)").length === 3, null, { timeout: 30000 });
await page.waitForTimeout(900);
await capture("ai", ".ai-title-card .ai-title-action.primary", ".ai-choice-grid", 1.1);

await page.locator(".ai-title-card .ai-title-action", { hasText: "Swaps" }).first().click();
await page.waitForSelector(".inline-substitution", { timeout: 20000 });
await capture("recipe", ".ingredient-swap.active", ".ingredients-card", 1.12);

await open("tab=pantry&pantryView=shopping");
await capture("shopping", ".pantry-shopping-item .shopping-check", ".pantry-shopping-groups", 1.1);

cooking = true;
await open("tab=home&voicePreview=speaking");
await page.click(".active-cooking-banner");
await page.waitForSelector(".voice-waveform", { timeout: 20000 });
await page.waitForTimeout(1600);
await capture("cooking", ".voice-waveform", ".cooking-voice-control", 1.16);
cooking = false;

await open("tab=home");
await capture("impact", ".impact-big strong", ".impact-panel", 1.1);

writeFileSync(STEPS_FILE, `${JSON.stringify(steps, null, 2)}\n`);
console.log(`Wrote ${Object.keys(steps).length} screens to public/walkthrough and ${STEPS_FILE}`);
await browser.close();
