import { useLayoutEffect, type RefObject } from 'react';

const MIN_SCALE = 0.62; // never shrink below this — past it, scrolling beats unreadable text
const BREATHING_ROOM = 16; // px kept free above/below

/**
 * Shrinks `ref`'s element (using CSS `zoom`, which — unlike transform — also
 * shrinks its layout box) just enough that it fits the window height, so
 * the sign-in / sign-up card never needs scrolling on short screens. On tall
 * screens it does nothing. Re-fits on resize and whenever the element's own
 * size changes (switching between sign in / sign up, an error appearing…).
 */
export function useFitToViewport(ref: RefObject<HTMLElement | null>) {
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;

    function fit() {
      if (!el) return;
      // Phones scroll instead: shrinking a tall form to 62% made the text tiny.
      if (window.innerWidth < 768) {
        el.style.zoom = '';
        return;
      }
      el.style.zoom = '1'; // measure at natural size…
      const natural = el.offsetHeight;
      const scale = natural > 0 ? Math.min(1, Math.max(MIN_SCALE, (window.innerHeight - BREATHING_ROOM) / natural)) : 1;
      el.style.zoom = scale >= 0.995 ? '' : scale.toFixed(3); // …then apply, before the browser paints
    }

    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(el);
    window.addEventListener('resize', fit);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', fit);
      el.style.zoom = '';
    };
  }, [ref]);
}
