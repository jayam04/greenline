export const getApiBase = () => {
  if (typeof window === "undefined") {
    return process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://backend:8000";
  }
  return process.env.NEXT_PUBLIC_API_URL || "";
};

let inMemoryToken: string | null = null;
let tokenGetterFn: (() => Promise<string | null | undefined>) | null = null;

export function getAuthToken(): string | null {
  if (inMemoryToken) return inMemoryToken;
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

export function setAuthToken(token: string | null) {
  inMemoryToken = token;
  if (typeof window !== "undefined") {
    if (token) {
      localStorage.setItem("token", token);
    } else {
      localStorage.removeItem("token");
    }
  }
}

export function removeAuthToken() {
  inMemoryToken = null;
  if (typeof window !== "undefined") {
    localStorage.removeItem("token");
  }
}

export function setTokenGetter(fn: (() => Promise<string | null | undefined>) | null) {
  tokenGetterFn = fn;
}

export async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  let token: string | null = null;
  if (tokenGetterFn) {
    try {
      token = (await tokenGetterFn()) ?? null;
    } catch {
      token = null;
    }
  }
  if (!token) {
    token = getAuthToken();
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };

  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const apiBase = getApiBase();
  const res = await fetch(`${apiBase}/api/v1${endpoint}`, {
    ...options,
    headers,
  });

  if (res.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    // If an Auth0 OAuth redirect callback is currently in flight in the URL query, do not navigate away
    const isCallback = Boolean(
      window.location.search &&
      window.location.search.includes("code=") &&
      window.location.search.includes("state=")
    );
    if (!isCallback) {
      removeAuthToken();
      window.location.href = "/login?error=session_expired";
    }
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => null);
    const message = err?.detail || `HTTP ${res.status}: ${res.statusText || "API Error"}`;
    throw new Error(message);
  }

  if (res.status === 204) {
    return {} as T;
  }

  return res.json();
}
