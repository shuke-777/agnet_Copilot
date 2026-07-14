import "@testing-library/jest-dom/vitest";

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

Object.defineProperty(globalThis, "ResizeObserver", {
  writable: true,
  value: ResizeObserverMock,
});

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }),
});

const originalGetComputedStyle = window.getComputedStyle;
window.getComputedStyle = ((element: Element, pseudoElement?: string | null) => {
  if (pseudoElement) {
    return originalGetComputedStyle(element);
  }
  return originalGetComputedStyle(element);
}) as typeof window.getComputedStyle;
