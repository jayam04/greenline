"use client";

import React, { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { Auth0Provider, Auth0Context, initialContext, useAuth0 } from "@auth0/auth0-react";
import { setTokenGetter, setAuthToken, apiFetch } from "@/lib/api";

function AuthSync({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, error, user, getAccessTokenSilently, getIdTokenClaims } = useAuth0();
  const [tokenReady, setTokenReady] = useState(false);
  const syncedRef = useRef<string | null>(null);
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";

  // Check if an OAuth redirect callback is currently in flight in the URL query
  const [hasCallbackCode, setHasCallbackCode] = useState(() => {
    if (typeof window === "undefined") return false;
    return Boolean(
      window.location.search &&
      window.location.search.includes("code=") &&
      window.location.search.includes("state=")
    );
  });

  useEffect(() => {
    if (isAuthenticated || error) {
      setHasCallbackCode(false);
    }
  }, [isAuthenticated, error]);

  // Register the silent token getter with apiFetch client (with ID token fallback)
  useEffect(() => {
    setTokenGetter(async () => {
      try {
        const token = await getAccessTokenSilently();
        if (token) {
          setAuthToken(token);
          return token;
        }
      } catch (err) {
        console.warn("getAccessTokenSilently fallback to getIdTokenClaims:", err);
      }
      try {
        const claims = await getIdTokenClaims();
        const idToken = claims?.__raw;
        if (idToken) {
          setAuthToken(idToken);
          return idToken;
        }
      } catch (err) {
        console.warn("getIdTokenClaims failed:", err);
      }
      return null;
    });

    return () => {
      setTokenGetter(null);
    };
  }, [getAccessTokenSilently, getIdTokenClaims]);

  // Eagerly acquire and store access token when user becomes authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      setTokenReady(false);
      return;
    }

    let active = true;
    const acquireInitialToken = async () => {
      try {
        const token = await getAccessTokenSilently();
        if (token && active) {
          setAuthToken(token);
          setTokenReady(true);
          return;
        }
      } catch (err) {
        console.warn("Initial getAccessTokenSilently failed, trying ID token fallback:", err);
      }

      try {
        const claims = await getIdTokenClaims();
        const idToken = claims?.__raw;
        if (idToken && active) {
          setAuthToken(idToken);
          setTokenReady(true);
          return;
        }
      } catch (err) {
        console.warn("Initial getIdTokenClaims failed:", err);
      }

      if (active) {
        setTokenReady(true);
      }
    };

    acquireInitialToken();

    return () => {
      active = false;
    };
  }, [isAuthenticated, getAccessTokenSilently, getIdTokenClaims]);

  useEffect(() => {
    if (!isAuthenticated || !user || !tokenReady) {
      syncedRef.current = null;
      return;
    }

    const userKey = `${user.sub || user.email}`;
    if (syncedRef.current === userKey) {
      return;
    }

    const syncUser = async () => {
      try {
        await apiFetch("/auth/sync", {
          method: "POST",
          body: JSON.stringify({
            email: user.email,
            name: user.name,
            picture: user.picture,
          }),
        });
        syncedRef.current = userKey;
      } catch (err) {
        console.error("Failed to sync user profile with backend:", err);
      }
    };

    syncUser();
  }, [isAuthenticated, user, tokenReady]);

  // Handle Auth0 authentication error on protected routes
  if (error && !isLoginPage) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 dark:bg-slate-950 p-4">
        <div className="bg-white dark:bg-slate-900 border border-rose-200 dark:border-rose-900/50 rounded-2xl p-6 max-w-md w-full shadow-lg text-center">
          <p className="text-sm font-bold text-rose-600 dark:text-rose-400 mb-2">Authentication Error</p>
          <p className="text-xs text-slate-600 dark:text-slate-400 mb-4">{error.message || "Failed to authenticate with Auth0"}</p>
          <a
            href="/login"
            className="inline-flex px-4 py-2 bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 text-xs font-bold rounded-lg hover:opacity-90"
          >
            Back to Login
          </a>
        </div>
      </div>
    );
  }

  // While Auth0 resolves authorization code callback or acquires token on protected routes, show loading state
  if (!isLoginPage && (hasCallbackCode || isLoading || (isAuthenticated && !tokenReady))) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 dark:bg-slate-950">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs font-bold text-slate-500 dark:text-slate-400">Authenticating with Auth0...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const domain = process.env.NEXT_PUBLIC_AUTH0_DOMAIN || "";
  const clientId = process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID || "";
  const audience = process.env.NEXT_PUBLIC_AUTH0_AUDIENCE || "http://localhost:8000";
  const redirectUri = typeof window !== "undefined" ? window.location.origin : undefined;

  // Gracefully render fallback context if Auth0 credentials are not configured (e.g. offline/mock tests)
  if (!domain || !clientId) {
    const fallbackContext = {
      ...(initialContext || {}),
      isAuthenticated: false,
      isLoading: false,
      user: undefined,
      loginWithRedirect: async () => {
        throw new Error("Auth0 is not configured. Please set NEXT_PUBLIC_AUTH0_DOMAIN and NEXT_PUBLIC_AUTH0_CLIENT_ID in your environment.");
      },
      logout: async () => {},
      getAccessTokenSilently: async () => null,
    };

    return (
      <Auth0Context.Provider value={fallbackContext as any}>
        {children}
      </Auth0Context.Provider>
    );
  }

  return (
    <Auth0Provider
      domain={domain}
      clientId={clientId}
      authorizationParams={{
        redirect_uri: redirectUri,
        audience: audience,
      }}
      onRedirectCallback={(appState) => {
        if (typeof window !== "undefined") {
          window.history.replaceState({}, document.title, window.location.pathname);
        }
      }}
      useRefreshTokens={true}
      cacheLocation="localstorage"
    >
      <AuthSync>{children}</AuthSync>
    </Auth0Provider>
  );
}
