import { describe, it, expect, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { FontProvider, useFont, FONT_STORAGE_KEY } from '@/components/FontProvider';

function TestComponent() {
  const { font, setFont } = useFont();
  return (
    <div>
      <span data-testid="current-font">{font}</span>
      <button onClick={() => setFont('inter')}>Set Inter</button>
      <button onClick={() => setFont('general-sans')}>Set General Sans</button>
    </div>
  );
}

describe('FontProvider', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = '';
    document.documentElement.removeAttribute('data-font');
  });

  it('defaults to general-sans when no font is stored in localStorage', () => {
    render(
      <FontProvider>
        <TestComponent />
      </FontProvider>
    );

    expect(screen.getByTestId('current-font').textContent).toBe('general-sans');
    expect(document.documentElement.getAttribute('data-font')).toBe('general-sans');
    expect(document.documentElement.classList.contains('font-general-sans')).toBe(true);
    expect(document.documentElement.classList.contains('font-inter')).toBe(false);
  });

  it('restores inter from localStorage if saved', () => {
    localStorage.setItem(FONT_STORAGE_KEY, 'inter');

    render(
      <FontProvider>
        <TestComponent />
      </FontProvider>
    );

    expect(screen.getByTestId('current-font').textContent).toBe('inter');
    expect(document.documentElement.getAttribute('data-font')).toBe('inter');
    expect(document.documentElement.classList.contains('font-inter')).toBe(true);
    expect(document.documentElement.classList.contains('font-general-sans')).toBe(false);
  });

  it('updates state, DOM attributes, classes, and localStorage when font is changed', () => {
    render(
      <FontProvider>
        <TestComponent />
      </FontProvider>
    );

    act(() => {
      fireEvent.click(screen.getByText('Set Inter'));
    });

    expect(screen.getByTestId('current-font').textContent).toBe('inter');
    expect(document.documentElement.getAttribute('data-font')).toBe('inter');
    expect(document.documentElement.classList.contains('font-inter')).toBe(true);
    expect(document.documentElement.classList.contains('font-general-sans')).toBe(false);
    expect(localStorage.getItem(FONT_STORAGE_KEY)).toBe('inter');

    act(() => {
      fireEvent.click(screen.getByText('Set General Sans'));
    });

    expect(screen.getByTestId('current-font').textContent).toBe('general-sans');
    expect(document.documentElement.getAttribute('data-font')).toBe('general-sans');
    expect(document.documentElement.classList.contains('font-general-sans')).toBe(true);
    expect(document.documentElement.classList.contains('font-inter')).toBe(false);
    expect(localStorage.getItem(FONT_STORAGE_KEY)).toBe('general-sans');
  });
});
