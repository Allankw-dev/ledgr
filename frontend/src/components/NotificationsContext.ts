import { createContext, useContext } from 'react';
import type { useUnreadNotifications } from '../hooks/useUnreadNotifications';

type Notifications = ReturnType<typeof useUnreadNotifications>;

const NotificationsContext = createContext<Notifications | null>(null);

/** The shell already runs the one notification poll; pages inside it read it from here instead of polling again. */
export const NotificationsProvider = NotificationsContext.Provider;

export function useShellNotifications(): Notifications | null {
  return useContext(NotificationsContext);
}
