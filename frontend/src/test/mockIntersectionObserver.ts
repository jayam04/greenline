import { vi } from 'vitest';

export class MockIntersectionObserver implements IntersectionObserver {
  readonly root: Element | Document | null;
  readonly rootMargin: string;
  readonly thresholds: ReadonlyArray<number>;
  callback: IntersectionObserverCallback;
  elements: Element[] = [];
  isDisconnected: boolean = false;
  static activeInstances: MockIntersectionObserver[] = [];

  constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
    this.callback = callback;
    this.root = options?.root ?? null;
    this.rootMargin = options?.rootMargin ?? '0px';
    this.thresholds = Array.isArray(options?.threshold)
      ? options?.threshold
      : [options?.threshold ?? 0];
    MockIntersectionObserver.activeInstances.push(this);
  }

  observe = vi.fn((el: Element) => {
    this.isDisconnected = false;
    if (!this.elements.includes(el)) {
      this.elements.push(el);
    }
    if (!MockIntersectionObserver.activeInstances.includes(this)) {
      MockIntersectionObserver.activeInstances.push(this);
    }
  });

  unobserve = vi.fn((el: Element) => {
    this.elements = this.elements.filter((e) => e !== el);
  });

  disconnect = vi.fn(() => {
    this.isDisconnected = true;
    this.elements = [];
    MockIntersectionObserver.activeInstances = MockIntersectionObserver.activeInstances.filter(
      (inst) => inst !== this
    );
  });

  takeRecords = vi.fn((): IntersectionObserverEntry[] => []);

  simulateIntersect(isIntersecting = true, elementIndex = 0) {
    if (this.isDisconnected || this.elements.length === 0) {
      return;
    }
    const target = this.elements[elementIndex];
    if (!target) {
      return;
    }
    const entry: IntersectionObserverEntry = {
      isIntersecting,
      target,
      intersectionRatio: isIntersecting ? 1 : 0,
      boundingClientRect: target.getBoundingClientRect ? target.getBoundingClientRect() : ({} as DOMRectReadOnly),
      intersectionRect: {} as DOMRectReadOnly,
      rootBounds: null,
      time: Date.now(),
    };
    this.callback([entry], this as unknown as IntersectionObserver);
  }

  static triggerLatest(isIntersecting = true, elementIndex = 0) {
    const latest = this.activeInstances[this.activeInstances.length - 1];
    if (latest) {
      latest.simulateIntersect(isIntersecting, elementIndex);
    }
  }

  static reset() {
    this.activeInstances = [];
  }
}
