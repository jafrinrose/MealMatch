// Full-stack browser smoke test for the running MealMatch application.
// Start the FastAPI backend on 127.0.0.1:8000 and Vite on 127.0.0.1:5173,
// then run `npm run test:system` from frontend/.
import { chromium } from "playwright-core";

const base = process.argv[2] || "http://127.0.0.1:5173";
const api = process.env.MEALMATCH_SYSTEM_API_URL || `${base}/api`;
const chrome = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const marker = `system-test-lentils-${Date.now()}`;
const browser = await chromium.launch({ executablePath: chrome, headless: true });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
await context.addInitScript(() => {
  sessionStorage.setItem("mealmatch-tour-shown", "1");
  sessionStorage.setItem("mealmatch-intro-seen", "1");
});
const page = await context.newPage();

function requireThat(condition, message) {
  if (!condition) throw new Error(message);
}

try {
  const apiResponse = await page.request.get(`${api}/`);
  requireThat(apiResponse.ok(), `Backend health request failed: ${apiResponse.status()}`);

  await page.goto(`${base}/?skipIntro=1&tab=home#app`, { waitUntil: "networkidle" });
  await page.locator(".app-frame").waitFor();

  requireThat(await page.locator("#main-content").count() === 1, "Main landmark is missing");
  requireThat(await page.getByRole("link", { name: "Skip to main content" }).count() === 1, "Skip link is missing");
  requireThat(await page.getByRole("navigation", { name: "Primary navigation" }).count() >= 1, "Labelled primary navigation is missing");

  await page.getByRole("button", { name: "Add ingredient" }).click();
  const dialog = page.getByRole("dialog", { name: "Add ingredients" });
  await dialog.getByLabel("Ingredient name").fill(marker);
  await dialog.getByRole("button", { name: "Add to pantry" }).click();
  await page.getByRole("status").filter({ hasText: "added to your pantry" }).waitFor();

  await page.getByRole("button", { name: "Pantry", exact: true }).first().click();
  await page.getByText(marker, { exact: false }).first().waitFor();
  requireThat(await page.locator('button[aria-current="page"]').first().textContent().then((value) => value?.includes("Pantry")), "Current navigation state was not exposed");

  // Search for a recipe the API currently lists, so the check follows the live catalogue.
  const recipesResponse = await page.request.get(`${api}/recipes?user_id=1`);
  requireThat(recipesResponse.ok(), "Recipes API could not be read");
  const listed = await recipesResponse.json();
  const target = (Array.isArray(listed) ? listed : listed.recipes)[0].title;
  await page.getByRole("button", { name: "Recipes", exact: true }).first().click();
  await page.getByRole("textbox", { name: "Search recipes" }).fill(target);
  await page.getByText(target, { exact: true }).first().waitFor();

  const pantryResponse = await page.request.get(`${api}/pantry/1`);
  requireThat(pantryResponse.ok(), "Pantry API could not be read for cleanup");
  const pantry = await pantryResponse.json();
  const created = pantry.find((item) => item.ingredient === marker);
  requireThat(Boolean(created), "Ingredient was visible in the UI but absent from the API");
  const cleanup = await page.request.delete(`${api}/pantry/item/${created.id}`);
  requireThat(cleanup.ok(), `System-test cleanup failed: ${cleanup.status()}`);

  console.log("PASS: API health, accessible shell, manual pantry entry, persistence, navigation and recipe search");
} finally {
  await browser.close();
}
