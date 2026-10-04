import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Testing Library only auto-cleans when test globals are on; we import explicitly instead.
afterEach(cleanup);

// jsdom has none of these browser APIs, and parts of the UI touch them on mount.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub;

if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
      dispatchEvent: () => false,
      onchange: null,
    }) as MediaQueryList;
}

window.HTMLElement.prototype.scrollIntoView = () => {};
