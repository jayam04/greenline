import type React from 'react';

export type StyleXStyles = Record<string, any> | undefined | null | false;

export interface StyleXProps {
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Creates StyleX style definitions using common CSS-compatible objects and tokens.
 */
export function create<T extends Record<string, React.CSSProperties | Record<string, any>>>(
  definitions: T
): T {
  return definitions;
}

/**
 * Combines StyleX rules and returns standard React element props { className, style }.
 */
export function props(...styles: (StyleXStyles | StyleXStyles[])[]): StyleXProps {
  const mergedStyle: Record<string, any> = {};
  const classNames: string[] = [];

  function processStyle(item: any) {
    if (!item || typeof item !== 'object') return;
    if (Array.isArray(item)) {
      item.forEach(processStyle);
      return;
    }

    if (item.className && typeof item.className === 'string') {
      classNames.push(item.className);
    }

    for (const [key, value] of Object.entries(item)) {
      if (key === 'className') continue;
      if (value !== undefined && value !== null) {
        mergedStyle[key] = value;
      }
    }
  }

  styles.forEach(processStyle);

  const result: StyleXProps = {};
  if (classNames.length > 0) {
    result.className = classNames.join(' ');
  }
  if (Object.keys(mergedStyle).length > 0) {
    result.style = mergedStyle as React.CSSProperties;
  }
  return result;
}

/**
 * StyleX attrs helper, mirroring props for attribute usage.
 */
export function attrs(...styles: (StyleXStyles | StyleXStyles[])[]): StyleXProps {
  return props(...styles);
}

/**
 * StyleX keyframes placeholder helper.
 */
export function keyframes(definitions: Record<string, React.CSSProperties>): string {
  return 'stylex-animation';
}

const stylex = {
  create,
  props,
  attrs,
  keyframes,
};

export default stylex;
