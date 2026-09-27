import axios from "axios";

// Vite proxies /api to FastAPI during local development. Keeping browser
// requests same-origin avoids masking backend errors as CORS failures.
// Deployments can still provide an absolute API URL through VITE_API_URL.
export const apiBaseUrl = import.meta.env.VITE_API_URL || "/api";

export const api = axios.create({ baseURL: apiBaseUrl });

// The server's explanation of a failed request ("That ingredient is already in your pantry."), or the fallback.
export function errorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" && detail.trim() ? detail : fallback;
}
