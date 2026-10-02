import { useCallback, useState } from 'react';

/**
 * Remembers whether a side panel is retracted, per browser, so it stays the
 * way the person left it between visits.
 */
export function useSidebarCollapsed(storageKey: string) {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(storageKey) === '1';
    } catch {
      return false;
    }
  });

  const toggle = useCallback(() => {
    setCollapsed((current) => {
      const next = !current;
      try {
        localStorage.setItem(storageKey, next ? '1' : '0');
      } catch {
        /* private mode / storage blocked — still works for this session */
      }
      return next;
    });
  }, [storageKey]);

  return [collapsed, toggle] as const;
}
