"use client";
import { useCallback, useEffect, useRef, useState } from "react";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:7860").replace(/\/$/, "");
export const GITHUB_URL = process.env.NEXT_PUBLIC_GITHUB_URL ?? "";
const TOKEN_KEY = "aarogya-owner-token";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export function getOwnerToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setOwnerToken(t: string | null) {
  try { if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ }
  window.dispatchEvent(new Event("owner-token"));
}

export async function api<T>(path: string, init: RequestInit & { owner?: boolean } = {}): Promise<T> {
  const { owner, ...rest } = init;
  const headers = new Headers(rest.headers);
  if (rest.body && !(rest.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (owner) { const t = getOwnerToken(); if (t) headers.set("X-Admin-Token", t); }
  let res: Response;
  try {
    res = await fetch(API_URL + path, { ...rest, headers, cache: "no-store" });
  } catch {
    throw new ApiError(0, "Can't reach the server. It may be starting up, so try again in a minute.");
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try { const j = await res.json(); if (typeof j.detail === "string") msg = j.detail; } catch { /* not json */ }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

/** Fetch hook with a "slow" flag: free hosting sleeps when idle, so the first request can take 30-60s. */
export function useApi<T>(path: string | null, pollMs?: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!path);
  const [slow, setSlow] = useState(false);
  const first = useRef(true);

  const load = useCallback(async () => {
    if (!path) return;
    const timer = first.current ? setTimeout(() => setSlow(true), 4000) : undefined;
    try {
      setData(await api<T>(path));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      clearTimeout(timer); setSlow(false); setLoading(false); first.current = false;
    }
  }, [path]);

  useEffect(() => { first.current = true; setLoading(!!path); load(); }, [load, path]);
  useEffect(() => {
    if (!pollMs) return;
    const id = setInterval(load, pollMs);
    return () => clearInterval(id);
  }, [load, pollMs]);

  return { data, error, loading, slow, reload: load };
}

export function useOwner() {
  const [token, setToken] = useState<string | null>(null);
  useEffect(() => {
    const sync = () => setToken(getOwnerToken());
    sync();
    window.addEventListener("owner-token", sync);
    return () => window.removeEventListener("owner-token", sync);
  }, []);
  return token;
}
