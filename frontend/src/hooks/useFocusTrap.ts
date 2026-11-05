import { useEffect, type RefObject } from 'react';

const FOCUSABLE =
  'a[href],button:not([disabled]),input:not([disabled]):not([type="hidden"]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

/**
 * Keyboard behaviour every dialog needs: focus moves into it when it opens, Tab and Shift+Tab stay inside it
 * instead of wandering onto the page behind, and focus returns to whatever opened it when it closes.
 */
export function useFocusTrap(ref: RefObject<HTMLElement | null>, active = true) {
  useEffect(() => {
    const root = ref.current;
    if (!active || !root) return;
    const previous = document.activeElement as HTMLElement | null;
    const items = () => Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));

    if (!root.hasAttribute('tabindex')) root.setAttribute('tabindex', '-1');
    // Prefer the first form field (so people can type straight away); otherwise the first control; otherwise the dialog.
    const firstField = root.querySelector<HTMLElement>('input:not([disabled]):not([type="hidden"]),select:not([disabled]),textarea:not([disabled])');
    (firstField ?? items()[0] ?? root).focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== 'Tab') return;
      const list = items();
      if (list.length === 0) {
        e.preventDefault();
        root!.focus();
        return;
      }
      const first = list[0];
      const last = list[list.length - 1];
      const current = document.activeElement;
      if (e.shiftKey && (current === first || current === root)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && current === last) {
        e.preventDefault();
        first.focus();
      }
    }
    root.addEventListener('keydown', onKeyDown);
    return () => {
      root.removeEventListener('keydown', onKeyDown);
      previous?.focus?.();
    };
  }, [ref, active]);
}
