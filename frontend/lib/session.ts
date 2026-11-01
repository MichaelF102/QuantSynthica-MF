"use client";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const KEY = "qsmf.token";

export type Me = { id: number; email: string };
export type Item = { id: number; kind: string; name: string; payload: Record<string, unknown>; updated_at: string | null };

export function getToken(): string | null { try { return localStorage.getItem(KEY); } catch { return null; } }
export function setToken(t: string | null) { try { if (t) localStorage.setItem(KEY, t); else localStorage.removeItem(KEY); } catch { /* storage unavailable */ } }

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const t = getToken();
  const r = await fetch(`${BASE}/api/v1${path}`, { ...init, headers: { "content-type": "application/json", ...(t ? { authorization: `Bearer ${t}` } : {}), ...init.headers } });
  if (r.status === 204) return undefined as T;
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(typeof body.detail === "string" ? body.detail : "Request failed"), { status: r.status });
  return body as T;
}

export const account = {
  register: (email: string, password: string) => call<{ token: string; user: Me }>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) => call<{ token: string; user: Me }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => call<Me>("/auth/me"),
  logout: () => call<void>("/auth/logout", { method: "POST" }),
  items: (kind?: string) => call<Item[]>(`/me/items${kind ? `?kind=${kind}` : ""}`),
  save: (kind: string, name: string, payload: Record<string, unknown>) => call<Item>(`/me/items/${kind}/${encodeURIComponent(name)}`, { method: "PUT", body: JSON.stringify(payload) }),
  remove: (id: number) => call<void>(`/me/items/${id}`, { method: "DELETE" }),
};
