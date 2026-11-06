"use client";

import React, { useEffect, useRef } from "react";
import { Auth0Provider, useAuth0 } from "@auth0/auth0-react";
import { setTokenGetter, setAuthToken, apiFetch } from "@/lib/api";

function AuthSync({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user, getAccessTokenSilently } = useAuth0();
  const syncedRef = useRef<string | null>(null);

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

  return <>{children}</>;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const domain = process.env.NEXT_PUBLIC_AUTH0_DOMAIN || "";
  const clientId = process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID || "";
  const audience = process.env.NEXT_PUBLIC_AUTH0_AUDIENCE || "http://localhost:8000";
  const redirectUri = typeof window !== "undefined" ? window.location.origin : undefined;

  // Gracefully render children if Auth0 credentials are not configured (e.g. offline/mock tests)
  if (!domain || !clientId) {
    return <>{children}</>;
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
