"use client";

import React, { createContext, useContext, useEffect, useState, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Auth0Provider, useAuth0, User as Auth0User } from "@auth0/auth0-react";
import { setAuthToken, removeAuthToken } from "@/lib/api";

interface GreenlineAuthContextType {
  isAuth0Enabled: boolean;
  isAuthenticated: boolean;
  isLoading: boolean;
  user: Auth0User | null;
  loginWithAuth0: () => Promise<void>;
  logout: () => Promise<void>;
}

const GreenlineAuthContext = createContext<GreenlineAuthContextType>({
  isAuth0Enabled: false,
  isAuthenticated: false,
  isLoading: false,
  user: null,
  loginWithAuth0: async () => {},
  logout: async () => {},
});

export function useGreenlineAuth() {
  return useContext(GreenlineAuthContext);
}

function Auth0SyncInner({ children }: { children: React.ReactNode }) {
  const {
    isAuthenticated,
    isLoading,
    user,
    getAccessTokenSilently,
    loginWithRedirect,
    logout: auth0Logout,
  } = useAuth0();

  const [tokenSynced, setTokenSynced] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function syncToken() {
      if (isAuthenticated) {
        try {
          const audience = process.env.NEXT_PUBLIC_AUTH0_AUDIENCE;
          const token = await getAccessTokenSilently({
            authorizationParams: audience ? { audience } : undefined,
          });
          if (isMounted && token) {
            setAuthToken(token);
            setTokenSynced(true);
          }
        } catch (err) {
          console.error("Failed to acquire Auth0 access token:", err);
        }
      }
    }

    syncToken();

    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, getAccessTokenSilently]);

  const handleLoginWithAuth0 = useCallback(async () => {
    const audience = process.env.NEXT_PUBLIC_AUTH0_AUDIENCE;
    await loginWithRedirect({
      authorizationParams: audience ? { audience } : undefined,
    });
  }, [loginWithRedirect]);

  const handleLogout = useCallback(async () => {
    removeAuthToken();
    await auth0Logout({
      logoutParams: {
        returnTo: typeof window !== "undefined" ? window.location.origin + "/login" : undefined,
      },
    });
  }, [auth0Logout]);

  const contextValue = useMemo<GreenlineAuthContextType>(() => ({
    isAuth0Enabled: true,
    isAuthenticated,
    isLoading: isLoading || (isAuthenticated && !tokenSynced),
    user: user || null,
    loginWithAuth0: handleLoginWithAuth0,
    logout: handleLogout,
  }), [isAuthenticated, isLoading, tokenSynced, user, handleLoginWithAuth0, handleLogout]);

  return (
    <GreenlineAuthContext.Provider value={contextValue}>
      {children}
    </GreenlineAuthContext.Provider>
  );
}

function LocalAuthFallback({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  const handleLogout = useCallback(async () => {
    removeAuthToken();
    router.push("/login");
  }, [router]);

  const contextValue = useMemo<GreenlineAuthContextType>(() => ({
    isAuth0Enabled: false,
    isAuthenticated: false,
    isLoading: false,
    user: null,
    loginWithAuth0: async () => {},
    logout: handleLogout,
  }), [handleLogout]);

  return (
    <GreenlineAuthContext.Provider value={contextValue}>
      {children}
    </GreenlineAuthContext.Provider>
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const domain = process.env.NEXT_PUBLIC_AUTH0_DOMAIN;
  const clientId = process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID;
  const isEnabled = process.env.NEXT_PUBLIC_AUTH0_ENABLED === "true";

  if (isEnabled && domain && clientId) {
    const redirectUri = typeof window !== "undefined" ? window.location.origin : "";
    const audience = process.env.NEXT_PUBLIC_AUTH0_AUDIENCE;

    return (
      <Auth0Provider
        domain={domain}
        clientId={clientId}
        authorizationParams={{
          redirect_uri: redirectUri,
          audience: audience || undefined,
        }}
        cacheLocation="localstorage"
        useRefreshTokens={true}
      >
        <Auth0SyncInner>{children}</Auth0SyncInner>
      </Auth0Provider>
    );
  }

  return <LocalAuthFallback>{children}</LocalAuthFallback>;
}
