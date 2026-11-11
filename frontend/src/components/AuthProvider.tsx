"use client";

import React, { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { Auth0Provider, Auth0Context, initialContext, useAuth0 } from "@auth0/auth0-react";
import { setTokenGetter, setAuthToken, apiFetch } from "@/lib/api";

function AuthSync({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, user, getAccessTokenSilently } = useAuth0();
  const syncedRef = useRef<string | null>(null);
  const pathname = usePathname();
  const isLoginPage = pathname === "/login";

  useEffect(() => {
    // Register the silent token getter with apiFetch client
    setTokenGetter(async () => {
      try {
        const token = await getAccessTokenSilently();
        if (token) {
          setAuthToken(token);
        }
        return token ?? null;
      } catch (err) {
        // Silently catch in case user is not logged in or token acquisition fails
        return null;
      }
    });

    return () => {
      setTokenGetter(null);
    };
  }, [getAccessTokenSilently]);

  // Eagerly acquire and store access token when user becomes authenticated
  useEffect(() => {
    if (isAuthenticated) {
      getAccessTokenSilently()
        .then((tok) => {
          if (tok) {
            setAuthToken(tok);
          }
        })
        .catch(() => {});
    }
  }, [isAuthenticated, getAccessTokenSilently]);

  useEffect(() => {
    if (!isAuthenticated || !user) {
      syncedRef.current = null;
      return;
    }

    const userKey = `${user.sub || user.email}`;
    if (syncedRef.current === userKey) {
      return;
    }

    const syncUser = async () => {
      try {
        const token = await getAccessTokenSilently();
        if (token) {
          setAuthToken(token);
        }
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
  }, [isAuthenticated, user, getAccessTokenSilently]);

  // While Auth0 resolves authorization code callback on protected routes, show loading state
  if (isLoading && !isLoginPage) {
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
      useRefreshTokens={true}
      cacheLocation="localstorage"
    >
      <AuthSync>{children}</AuthSync>
    </Auth0Provider>
  );
}
