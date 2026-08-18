import { API_BASE_URL, request } from "./client.js";

export function fetchNews({ category, signal } = {}) {
  const categoryQuery = category
    ? `?category=${encodeURIComponent(category)}`
    : "";

  return request(`${API_BASE_URL}/news${categoryQuery}`, { signal });
}
