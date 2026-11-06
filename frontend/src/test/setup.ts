import '@testing-library/jest-dom';
import React from 'react';
import { vi } from 'vitest';

// Mock matchMedia for jsdom
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock Next.js router
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/',
}));

// Mock Next.js fonts
vi.mock('next/font/google', () => ({
  Inter: () => ({
    className: 'mock-font-inter',
    variable: '--font-inter',
  }),
  Figtree: () => ({
    className: 'mock-font-figtree',
    variable: '--font-heading-figtree',
  }),
}));

vi.mock('next/font/local', () => ({
  default: () => ({
    className: 'mock-font-general-sans',
    variable: '--font-general-sans',
  }),
}));

// Mock Auth0 React SDK for offline test execution
vi.mock('@auth0/auth0-react', () => ({
  useAuth0: () => ({
    isAuthenticated: true,
    isLoading: false,
    user: {
      sub: 'auth0|test_user',
      email: 'test@example.com',
      name: 'Test User',
      picture: 'https://example.com/avatar.png',
    },
    loginWithRedirect: vi.fn(),
    logout: vi.fn(),
    getAccessTokenSilently: vi.fn().mockResolvedValue('mock-auth0-access-token'),
  }),
  Auth0Provider: ({ children }: { children: React.ReactNode }) => children,
}));
