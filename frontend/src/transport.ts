import { isTauri } from "@tauri-apps/api/core";
import { apiUrl, normalizeServer } from "./server.ts";

export const desktop = isTauri();
const serverKey = "finesub-review.server";
let server = "";

export function savedServer(): string {
  return localStorage.getItem(serverKey) || "";
}

export function selectServer(value: string): void {
  server = normalizeServer(value);
  if (savedServer() !== server) location.hash = "";
  localStorage.setItem(serverKey, server);
}

export function scopedDraftKey(key: string): string {
  return desktop ? `${server}:${key}` : key;
}

export async function request(path: string, options: RequestInit = {}): Promise<Response> {
  if (!desktop) return fetch("/api" + path, { ...options, credentials: "same-origin" });
  const { fetch: nativeFetch } = await import("@tauri-apps/plugin-http");
  try {
    return await nativeFetch(apiUrl(server, path), {
      ...options,
      credentials: "include",
      connectTimeout: 15_000,
      maxRedirections: 0,
      signal: options.signal || AbortSignal.timeout(120_000),
    });
  } catch {
    throw new Error("无法连接审核服务器，请检查网络、服务器地址和 HTTPS 证书");
  }
}

export async function probeServer(value: string): Promise<void> {
  const { fetch: nativeFetch } = await import("@tauri-apps/plugin-http");
  const response = await nativeFetch(apiUrl(value, "/bootstrap"), {
    connectTimeout: 10_000,
    maxRedirections: 0,
    signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) throw new Error(`连接失败（HTTP ${response.status}）`);
  const body = await response.json();
  if (typeof body.initialized !== "boolean" || typeof body.access_configured !== "boolean")
    throw new Error("该地址不是兼容的 FineSub 审核服务");
}
