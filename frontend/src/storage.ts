import { useEffect, useState } from "react";

// Browser storage can be unavailable (private mode, blocked site data); the app then works without it.
export function readStorage(key: string, where: "local" | "session" = "local") {
  try { return (where === "session" ? sessionStorage : localStorage).getItem(key); } catch { return null; }
}

export function writeStorage(key: string, value: string | null, where: "local" | "session" = "local") {
  try {
    const storage = where === "session" ? sessionStorage : localStorage;
    if (value === null) storage.removeItem(key);
    else storage.setItem(key, value);
  } catch { /* not stored: the setting lasts until the page closes */ }
}

// State that survives a reload: session storage lasts while the tab is open, local storage
// until cleared. Without storage this is plain state.
export function useStoredState<T>(key: string, initial: T, where: "session" | "local") {
  const [value, setValue] = useState<T>(() => {
    try {
      const saved = readStorage(key, where);
      return saved ? JSON.parse(saved) as T : initial;
    } catch { return initial; }
  });
  useEffect(() => writeStorage(key, value === null ? null : JSON.stringify(value), where), [key, value, where]);
  return [value, setValue] as const;
}
