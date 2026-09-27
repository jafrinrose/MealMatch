import { useState } from "react";
import type { UserPreferences } from "../types";
import { titleCase } from "../utils";
import { PageHeader, Icon } from "../components/ui";

const dietaryOptions = [
  "vegetarian",
  "vegan",
  "pescatarian",
  "gluten-free",
  "dairy-free",
  "keto",
  "paleo",
  "halal",
  "kosher",
];
const allergyOptions = ["peanuts", "tree nuts", "shellfish", "dairy", "eggs", "soy", "gluten", "fish", "sesame"];
const cuisineOptions = ["italian", "asian", "mexican", "mediterranean", "indian", "american", "middle eastern", "french", "japanese", "thai"];
export function SettingsScreen({ preferences, darkMode, onThemeChange, onSave }: { preferences: UserPreferences; darkMode: boolean; onThemeChange: (enabled: boolean) => void; onSave: (preferences: Omit<UserPreferences, "user_id" | "onboarding_complete">) => Promise<void> }) {
  const [form, setForm] = useState(preferences);
  const [saving, setSaving] = useState(false);
  function toggle(field: "dietary_restrictions" | "allergies" | "preferred_cuisines", value: string) {
    setForm((current) => ({ ...current, [field]: current[field].includes(value) ? current[field].filter((item) => item !== value) : [...current[field], value] }));
  }
  async function save() {
    setSaving(true);
    try {
      await onSave({ dietary_restrictions: form.dietary_restrictions, allergies: form.allergies, disliked_ingredients: form.disliked_ingredients, preferred_cuisines: form.preferred_cuisines, max_cooking_time: form.max_cooking_time, skill_level: form.skill_level });
    } finally { setSaving(false); }
  }
  return (
    <div className="screen settings-screen">
      <PageHeader eyebrow="Make MealMatch yours" title="Settings" subtitle="Preferences are used to personalise every match" />
      <section className="theme-card"><span className="settings-icon"><Icon name={darkMode ? "moon" : "sun"} /></span><div><h3>Appearance</h3><p>{darkMode ? "Dark mode" : "Light mode"}</p></div><button className={`toggle ${darkMode ? "on" : ""}`} onClick={() => onThemeChange(!darkMode)} aria-label="Toggle colour theme"><span /></button></section>
      <section className="settings-section"><p className="eyebrow"><Icon name="sparkles" /> Cooking preferences</p><h2>Dietary preferences</h2><ChipGroup options={dietaryOptions} selected={form.dietary_restrictions} onToggle={(value) => toggle("dietary_restrictions", value)} /><OtherPreferenceInput label="Add another dietary preference" onAdd={(value) => setForm((current) => ({ ...current, dietary_restrictions: Array.from(new Set([...current.dietary_restrictions, value])) }))} /></section>
      <section className="settings-section"><h2>Allergies</h2><p className="settings-helper">We’ll keep these ingredients out of your recommendations.</p><ChipGroup options={allergyOptions} selected={form.allergies} onToggle={(value) => toggle("allergies", value)} /><OtherPreferenceInput label="Add another allergy" onAdd={(value) => setForm((current) => ({ ...current, allergies: Array.from(new Set([...current.allergies, value])) }))} /></section>
      <section className="settings-section"><h2>Cuisine preferences</h2><ChipGroup options={cuisineOptions} selected={form.preferred_cuisines} onToggle={(value) => toggle("preferred_cuisines", value)} /><OtherPreferenceInput label="Add another cuisine" onAdd={(value) => setForm((current) => ({ ...current, preferred_cuisines: Array.from(new Set([...current.preferred_cuisines, value])) }))} /></section>
      <section className="settings-section"><h2>Cooking skill level</h2><div className="skill-options">{[{ id: "beginner", note: "Simple, guided recipes" }, { id: "intermediate", note: "Comfortable in the kitchen" }, { id: "advanced", note: "I love a challenge" }].map((skill) => <button className={form.skill_level === skill.id ? "active" : ""} onClick={() => setForm({ ...form, skill_level: skill.id })} key={skill.id}><span className="radio-dot" /><div><strong>{titleCase(skill.id)}</strong><small>{skill.note}</small></div></button>)}</div></section>
      <button className="primary-button save-settings" disabled={saving} onClick={() => void save()}>{saving ? "Saving…" : "Update preferences"}</button>
    </div>
  );
}

function ChipGroup({ options, selected, onToggle }: { options: string[]; selected: string[]; onToggle: (option: string) => void }) {
  const visibleOptions = Array.from(new Set([...options, ...selected]));
  return <div className="chip-group">{visibleOptions.map((option) => <button className={selected.includes(option) ? "active" : ""} key={option} onClick={() => onToggle(option)}>{selected.includes(option) && <Icon name="check" />}{titleCase(option)}</button>)}</div>;
}

function OtherPreferenceInput({ label, onAdd }: { label: string; onAdd: (value: string) => void }) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  function add() {
    const cleaned = value.trim().toLowerCase();
    if (!cleaned) return;
    onAdd(cleaned);
    setValue("");
    setOpen(false);
  }
  return open ? <div className="other-preference"><input autoFocus value={value} onChange={(event) => setValue(event.target.value)} placeholder={label} onKeyDown={(event) => event.key === "Enter" && add()} /><button onClick={add}>Add</button><button onClick={() => setOpen(false)} aria-label="Cancel"><Icon name="close" /></button></div> : <button className="other-preference-trigger" onClick={() => setOpen(true)}><Icon name="plus" /> Other</button>;
}
