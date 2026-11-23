import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MockIntersectionObserver } from './mockIntersectionObserver';

describe('MockIntersectionObserver fidelity', () => {
  beforeEach(() => {
    MockIntersectionObserver.reset();
  });

  it('tracks observed elements and triggers callback on simulateIntersect', () => {
    const callback = vi.fn();
    const observer = new MockIntersectionObserver(callback);
    const div = document.createElement('div');

    expect(MockIntersectionObserver.activeInstances).toContain(observer);
    expect(observer.isDisconnected).toBe(false);

    observer.observe(div);
    expect(observer.elements).toContain(div);

    observer.simulateIntersect(true);
    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback.mock.calls[0][0][0].target).toBe(div);
    expect(callback.mock.calls[0][0][0].isIntersecting).toBe(true);
  });

  it('unobserve removes target element from elements list', () => {
    const callback = vi.fn();
    const observer = new MockIntersectionObserver(callback);
    const div1 = document.createElement('div');
    const div2 = document.createElement('div');

    observer.observe(div1);
    observer.observe(div2);
    expect(observer.elements.length).toBe(2);

    observer.unobserve(div1);
    expect(observer.elements).toEqual([div2]);
  });

  it('disconnect marks instance as disconnected, clears elements, and removes from activeInstances', () => {
    const callback = vi.fn();
    const observer = new MockIntersectionObserver(callback);
    const div = document.createElement('div');

    observer.observe(div);
    expect(MockIntersectionObserver.activeInstances).toContain(observer);

    observer.disconnect();
    expect(observer.isDisconnected).toBe(true);
    expect(observer.elements.length).toBe(0);
    expect(MockIntersectionObserver.activeInstances).not.toContain(observer);

    // simulateIntersect must NOT fire callback after disconnect
    observer.simulateIntersect(true);
    expect(callback).not.toHaveBeenCalled();

    // triggerLatest must NOT fire disconnected instance
    MockIntersectionObserver.triggerLatest(true);
    expect(callback).not.toHaveBeenCalled();
  });

  it('simulateIntersect does not fire callback when elements array is empty', () => {
    const callback = vi.fn();
    const observer = new MockIntersectionObserver(callback);

    observer.simulateIntersect(true);
    expect(callback).not.toHaveBeenCalled();
  });
});
