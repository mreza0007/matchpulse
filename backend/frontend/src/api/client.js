export const API_BASE_URL = import.meta.env.VITE_API_URL;

export function request(url, options) {
  return fetch(url, options);
}
