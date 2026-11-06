import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import * as auth0 from '@auth0/auth0-react';
import { apiFetch, getAuthToken, setAuthToken, removeAuthToken, setTokenGetter } from '@/lib/api';
import { AuthProvider } from '@/components/AuthProvider';
import LoginPage from '@/app/login/page';
import { Sidebar } from '@/components/Sidebar';
import { ThemeProvider } from '@/components/ThemeProvider';

const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
  usePathname: () => '/',
}));

describe('Auth0 & API Client Integration', () => {
  const mockLoginWithRedirect = vi.fn();
  const mockLogout = vi.fn();
  const mockGetAccessTokenSilently = vi.fn().mockResolvedValue('mock-auth0-access-token');

  beforeEach(() => {
    vi.clearAllMocks();
    removeAuthToken();
    setTokenGetter(null);

    // Default authenticated mock
    vi.spyOn(auth0, 'useAuth0').mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: {
        sub: 'auth0|test_user',
        email: 'test@example.com',
        name: 'Test User',
        picture: 'https://example.com/avatar.png',
      },
      loginWithRedirect: mockLoginWithRedirect,
      logout: mockLogout,
      getAccessTokenSilently: mockGetAccessTokenSilently,
      getIdTokenClaims: vi.fn(),
      loginWithPopup: vi.fn(),
      handleRedirectCallback: vi.fn(),
    } as any);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('apiFetch token injection and 401 handling', () => {
    it('injects Bearer token from setAuthToken into outgoing requests', async () => {
      setAuthToken('test-sync-token-123');

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ success: true }),
      });
      global.fetch = mockFetch;

      const result = await apiFetch('/test-endpoint');
      expect(result).toEqual({ success: true });
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/test-endpoint'),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-sync-token-123',
          }),
        })
      );
    });

    it('injects Bearer token from registered tokenGetter', async () => {
      setTokenGetter(async () => 'dynamic-auth0-jwt');

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ data: 'ok' }),
      });
      global.fetch = mockFetch;

      const result = await apiFetch('/accounts');
      expect(result).toEqual({ data: 'ok' });
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/accounts'),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer dynamic-auth0-jwt',
          }),
        })
      );
    });

    it('handles 401 Unauthorized by removing token and redirecting to /login', async () => {
      setAuthToken('expired-token');

      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Unauthorized' }),
      });
      global.fetch = mockFetch;

      // Mock window.location
      const originalLocation = window.location;
      delete (window as any).location;
      window.location = {
        ...originalLocation,
        pathname: '/investments',
        href: 'http://localhost:3000/investments',
      } as any;

      await expect(apiFetch('/protected-resource')).rejects.toThrow('Unauthorized');
      expect(getAuthToken()).toBeNull();
      expect(window.location.href).toBe('/login');

      (window as any).location = originalLocation;
    });
  });

  describe('Sidebar user profile and logout', () => {
    it('displays authenticated user name, email, and avatar', () => {
      render(
        <ThemeProvider>
          <Sidebar />
        </ThemeProvider>
      );

      expect(screen.getByText('Test User')).toBeInTheDocument();
      expect(screen.getByText('test@example.com')).toBeInTheDocument();
      const avatar = screen.getByAltText('Test User');
      expect(avatar).toHaveAttribute('src', 'https://example.com/avatar.png');
    });

    it('triggers Auth0 logout and clears token on logout click', () => {
      setAuthToken('active-token');

      render(
        <ThemeProvider>
          <Sidebar />
        </ThemeProvider>
      );

      const logoutBtns = screen.getAllByRole('button', { name: /log out/i });
      fireEvent.click(logoutBtns[0]);

      expect(getAuthToken()).toBeNull();
      expect(mockLogout).toHaveBeenCalledWith(
        expect.objectContaining({
          logoutParams: expect.objectContaining({
            returnTo: expect.any(String),
          }),
        })
      );
    });
  });

  describe('Login Page Auth0 flow', () => {
    it('renders Continue with Auth0 button and calls loginWithRedirect on click', () => {
      // In this test, isAuthenticated is false initially
      vi.spyOn(auth0, 'useAuth0').mockReturnValue({
        isAuthenticated: false,
        isLoading: false,
        user: undefined,
        loginWithRedirect: mockLoginWithRedirect,
        logout: mockLogout,
        getAccessTokenSilently: mockGetAccessTokenSilently,
        getIdTokenClaims: vi.fn(),
        loginWithPopup: vi.fn(),
        handleRedirectCallback: vi.fn(),
      } as any);

      render(<LoginPage />);

      const auth0Button = screen.getByRole('button', { name: /continue with auth0/i });
      expect(auth0Button).toBeInTheDocument();

      fireEvent.click(auth0Button);
      expect(mockLoginWithRedirect).toHaveBeenCalled();
    });

    it('redirects to / when already authenticated', () => {
      render(<LoginPage />);
      expect(mockPush).toHaveBeenCalledWith('/');
    });
  });

  describe('AuthProvider', () => {
    it('gracefully renders children when Auth0 domain/client_id is not set', () => {
      const originalDomain = process.env.NEXT_PUBLIC_AUTH0_DOMAIN;
      const originalClient = process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID;

      delete process.env.NEXT_PUBLIC_AUTH0_DOMAIN;
      delete process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID;

      render(
        <AuthProvider>
          <div data-testid="child-content">App Body</div>
        </AuthProvider>
      );

      expect(screen.getByTestId('child-content')).toHaveTextContent('App Body');

      process.env.NEXT_PUBLIC_AUTH0_DOMAIN = originalDomain;
      process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID = originalClient;
    });

    it('registers token getter and syncs profile when configured and authenticated', async () => {
      process.env.NEXT_PUBLIC_AUTH0_DOMAIN = 'test.eu.auth0.com';
      process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID = 'test-client-id';

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ user_id: 1, email: 'test@example.com' }),
      });
      global.fetch = mockFetch;

      render(
        <AuthProvider>
          <div data-testid="protected-content">Protected Content</div>
        </AuthProvider>
      );

      expect(screen.getByTestId('protected-content')).toBeInTheDocument();

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/v1/auth/sync'),
          expect.objectContaining({
            method: 'POST',
            body: JSON.stringify({
              email: 'test@example.com',
              name: 'Test User',
              picture: 'https://example.com/avatar.png',
            }),
          })
        );
      });
    });
  });
});
