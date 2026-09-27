import { useState } from "react";
import type { PantryItem, ShoppingItem, Recipe } from "../types";
import { pantryCategories, titleCase, categoryEmoji, normalizedCategory, expiryStatus } from "../utils";
import { PageHeader, EmptyState, Icon } from "../components/ui";
import { IngredientEmoji } from "../components/FoodArt";

export function PantryScreen({ items, recipes, shoppingList, onAdd, onEdit, onRemove, onToggleShopping, onRemoveShopping, onRemoveList, onClearList }: { items: PantryItem[]; recipes: Recipe[]; shoppingList: ShoppingItem[]; onAdd: () => void; onEdit: (item: PantryItem) => void; onRemove: (id: number) => void; onToggleShopping: (itemId: number) => Promise<void>; onRemoveShopping: (itemId: number) => Promise<void>; onRemoveList: (recipeId: number | null) => Promise<void>; onClearList: () => Promise<void> }) {
  const [confirmClear, setConfirmClear] = useState(false);
  const [view, setView] = useState<"pantry" | "shopping">(() => new URLSearchParams(window.location.search).get("pantryView") === "shopping" ? "shopping" : "pantry");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const filtered = items.filter((item) => {
    const matchesSearch = item.ingredient.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = category === "all" || normalizedCategory(item.category, item.ingredient) === category;
    return matchesSearch && matchesCategory;
  });
  const expiring = items.filter((item) => expiryStatus(item.expiry_date).urgent).length;
  const remainingShoppingItems = shoppingList.filter((item) => !item.checked).length;
  const completedShoppingItems = shoppingList.length - remainingShoppingItems;
  const shoppingProgress = shoppingList.length ? Math.round((completedShoppingItems / shoppingList.length) * 100) : 0;
  const recipeNames = new Map(recipes.map((recipe) => [recipe.id, recipe.title]));
  const groupedShopping = Array.from(shoppingList.reduce((groups, item) => {
    const key = item.recipe_id == null ? "other" : String(item.recipe_id);
    const group = groups.get(key) || {
      key,
      title: item.recipe_id == null ? "Other groceries" : recipeNames.get(item.recipe_id) || "Recipe ingredients",
      items: [] as ShoppingItem[],
    };
    group.items.push(item);
    groups.set(key, group);
    return groups;
  }, new Map<string, { key: string; title: string; items: ShoppingItem[] }>()).values());

  return (
    <div className="screen pantry-screen">
      <PageHeader eyebrow="Everything in one place" title="My pantry" subtitle={view === "pantry" ? `${items.length} item${items.length === 1 ? "" : "s"} · ${expiring} to use soon` : `${remainingShoppingItems} item${remainingShoppingItems === 1 ? "" : "s"} left to pick up`} action={<button className="primary-button header-button" onClick={onAdd}><Icon name="plus" /> Add food</button>} />
      <div className="pantry-view-toggle" role="tablist" aria-label="Pantry view">
        <button className={view === "pantry" ? "active" : ""} role="tab" aria-selected={view === "pantry"} onClick={() => setView("pantry")}><Icon name="pantry" /> My pantry <span>{items.length}</span></button>
        <button className={view === "shopping" ? "active" : ""} role="tab" aria-selected={view === "shopping"} onClick={() => setView("shopping")}><span className="cart-symbol">🛒</span> Shopping list <span>{remainingShoppingItems}</span></button>
      </div>
      {view === "pantry" ? <>
        <div className="search-field"><Icon name="search" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search ingredients…" /></div>
        <div className="filter-scroll">
          {pantryCategories.map((option) => {
            const count = option === "all" ? items.length : items.filter((item) => normalizedCategory(item.category, item.ingredient) === option).length;
            return <button className={category === option ? "active" : ""} onClick={() => setCategory(option)} key={option}>{categoryEmoji(option)} {titleCase(option)} <span>{count}</span></button>;
          })}
        </div>
        {filtered.length > 0 ? (
          <div className="pantry-list">
            {filtered.map((item) => {
              const status = expiryStatus(item.expiry_date);
              return (
                <article className="pantry-item" key={item.id}>
                  <IngredientEmoji name={item.ingredient} />
                  <div className="pantry-item-copy"><h3>{titleCase(item.ingredient)}</h3><p>{item.quantity || "Quantity not set"}</p><span className={status.urgent ? "urgent" : ""}>{status.urgent ? <Icon name="alert" /> : <Icon name="check" />}{status.label}{item.expiry_estimated ? " · estimated" : ""}</span></div>
                  <div className="item-actions">
                    <button onClick={() => onEdit(item)} aria-label={`Edit ${item.ingredient}`}><Icon name="edit" /></button>
                    <button onClick={() => onRemove(item.id)} aria-label={`Delete ${item.ingredient}`}><Icon name="trash" /></button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : <EmptyState icon="pantry" title="Nothing found here" text={items.length ? "Try a different search or category." : "Start with what is already in your fridge."} action="Add an ingredient" onAction={onAdd} />}
      </> : (
        <section className="pantry-shopping-view" aria-label="Shopping list">
          {shoppingList.length > 0 ? <>
            <div className="shopping-list-summary">
              <div><span className="shopping-summary-icon">🛒</span><div><p className="eyebrow">Ready for your next shop</p><h2>{remainingShoppingItems} item{remainingShoppingItems === 1 ? "" : "s"} left</h2><span>{completedShoppingItems} of {shoppingList.length} picked up · lists clear themselves when everything is ticked</span></div></div>
              <strong>{shoppingProgress}%</strong>
            </div>
            <div className={`shopping-clear${confirmClear ? " confirming" : ""}`}>
              {confirmClear ? <>
                <span>Delete all {shoppingList.length} item{shoppingList.length === 1 ? "" : "s"} on your list?</span>
                <button className="danger" onClick={() => void onClearList().finally(() => setConfirmClear(false))}><Icon name="trash" /> Delete list</button>
                <button onClick={() => setConfirmClear(false)}>Keep it</button>
              </> : <button onClick={() => setConfirmClear(true)}><Icon name="trash" /> Delete entire list</button>}
            </div>
            <div className="shopping-list-progress" aria-label={`${shoppingProgress}% of shopping completed`}><span style={{ width: `${shoppingProgress}%` }} /></div>
            <div className="pantry-shopping-groups">
              {groupedShopping.map((group) => (
                <article className={`pantry-shopping-group${group.items.every((item) => item.checked) ? " is-complete" : ""}`} key={group.key}>
                  <header><div><span>🍽️</span><div><p>Added for</p><h3>{group.title}</h3></div></div><strong>{group.items.filter((item) => !item.checked).length} left</strong><button className="delete-meal-list" aria-label={`Delete shopping list for ${group.title}`} onClick={() => void onRemoveList(group.key === "other" ? null : Number(group.key))}><Icon name="trash" /> Delete list</button></header>
                  <div>
                    {group.items.map((item) => (
                      <div className={`pantry-shopping-item${item.checked ? " checked" : ""}`} key={item.id}>
                        <button className="shopping-check" aria-label={item.checked ? `Mark ${item.ingredient} as still needed` : `Mark ${item.ingredient} as picked up`} aria-pressed={item.checked} onClick={() => void onToggleShopping(item.id)}>{item.checked && <Icon name="check" />}</button>
                        <IngredientEmoji name={item.ingredient} small />
                        <div className="shopping-item-copy"><strong>{titleCase(item.ingredient)}</strong><small>{item.checked ? "Picked up" : "Still needed"}</small></div>
                        <span className="shopping-item-quantity">{item.quantity || "1 portion"}</span>
                        <button className="remove-shopping-item" aria-label={`Remove ${item.ingredient} from shopping list`} onClick={() => void onRemoveShopping(item.id)}><Icon name="trash" /></button>
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </> : <EmptyState icon="pantry" title="Your shopping list is clear" text="Add missing ingredients from a recipe and MealMatch will organise them here by meal." />}
        </section>
      )}
    </div>
  );
}
