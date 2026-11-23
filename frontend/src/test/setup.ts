import '@testing-library/jest-dom';
import React from 'react';
import { vi } from 'vitest';
import { MockIntersectionObserver } from './mockIntersectionObserver';

// Mock IntersectionObserver globally for tests
if (typeof window !== 'undefined') {
  (window as any).IntersectionObserver = MockIntersectionObserver;
}
if (typeof global !== 'undefined') {
  (global as any).IntersectionObserver = MockIntersectionObserver;
}

// Mock ResizeObserver if not provided by jsdom
if (typeof window !== 'undefined' && typeof (window as any).ResizeObserver === 'undefined') {
  class MockResizeObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
  }
  (window as any).ResizeObserver = MockResizeObserver;
  (global as any).ResizeObserver = MockResizeObserver;
}

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
  useSearchParams: () => new URLSearchParams(typeof window !== 'undefined' ? window.location.search : ''),
  usePathname: () => (typeof window !== 'undefined' ? window.location.pathname : '/'),
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
  Spline_Sans: () => ({
    className: 'mock-font-spline-sans',
    variable: '--font-spline-sans',
  }),
}));

vi.mock('next/font/local', () => ({
  default: () => ({
    className: 'mock-font-general-sans',
    variable: '--font-general-sans',
  }),
}));

// Mock Auth0 React SDK for offline test execution
const defaultMockAuth0State = {
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
  getIdTokenClaims: vi.fn().mockResolvedValue({
    __raw: 'mock-auth0-id-token',
    sub: 'auth0|test_user',
  }),
};

const Auth0Context = React.createContext(defaultMockAuth0State);

vi.mock('@auth0/auth0-react', () => ({
  Auth0Context,
  initialContext: {
    isAuthenticated: false,
    isLoading: true,
    user: undefined,
    loginWithRedirect: vi.fn(),
    logout: vi.fn(),
    getAccessTokenSilently: vi.fn().mockResolvedValue(null),
  },
  useAuth0: () => defaultMockAuth0State,
  Auth0Provider: ({ children }: { children: React.ReactNode }) => children,
}));
