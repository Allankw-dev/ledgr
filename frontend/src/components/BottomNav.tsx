import type { LucideIcon } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';

export interface BottomNavItem {
  label: string;
  icon: LucideIcon;
  /** Route this tab goes to. Omit for a button-style tab (e.g. "Menu"). */
  to?: string;
  /** Extra path prefixes that also mark this tab as the current one. */
  also?: string[];
  onClick?: () => void;
  badge?: number;
  badgeTone?: 'green' | 'amber';
  /** Raised, glowing hero tab (used for the assistant). */
  center?: boolean;
}

/**
 * Floating glass dock for phones. The highlight pill glides to whichever tab
 * is current; one tab can be raised in the middle as the hero action.
 * Hidden from md up, where the sidebar / top tabs take over.
 */
export function BottomNav({ items }: { items: BottomNavItem[] }) {
  const { pathname } = useLocation();
  const n = items.length;
  const activeIndex = items.findIndex((i) => i.to && [i.to, ...(i.also ?? [])].some((p) => pathname.startsWith(p)));
  const activeItem = activeIndex >= 0 ? items[activeIndex] : null;

  return (
    <nav aria-label="Main" className="md:hidden fixed inset-x-3 z-40 bottom-[max(0.75rem,env(safe-area-inset-bottom))]">
      <div className="bottom-nav relative grid rounded-[26px]" style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}>
        {activeItem && !activeItem.center && (
          <span
            aria-hidden="true"
            className="bottom-nav-pill absolute top-1.5 bottom-1.5 left-0 px-1 pointer-events-none"
            style={{ width: `${100 / n}%`, transform: `translateX(${activeIndex * 100}%)` }}
          >
            <span className="block h-full rounded-[20px] bg-emerald-100 ring-1 ring-green/25 shadow-[0_0_20px_-4px_rgba(57,255,136,0.55)]" />
          </span>
        )}

        {items.map((item, i) => {
          const active = i === activeIndex;
          const Icon = item.icon;
          const inner = (
            <>
              {item.center ? (
                <span className="nav-center-orb relative -mt-6 w-12 h-12 rounded-full bg-gradient-to-br from-emerald-700 to-cyan text-[#06110B] flex items-center justify-center">
                  <Icon className="w-6 h-6" strokeWidth={2} />
                </span>
              ) : (
                <span className="relative">
                  <Icon key={String(active)} className={`w-[22px] h-[22px] ${active ? 'nav-pop' : ''}`} strokeWidth={active ? 2.25 : 1.75} />
                  {!!item.badge && item.badge > 0 && (
                    <span
                      className={`pop-in absolute -top-1.5 -right-2.5 min-w-[16px] h-4 px-1 rounded-full text-[10px] font-bold leading-4 text-center text-[#06110B] ${
                        item.badgeTone === 'amber' ? 'bg-amber' : 'bg-green'
                      }`}
                    >
                      {item.badge > 9 ? '9+' : item.badge}
                    </span>
                  )}
                </span>
              )}
              <span className={`text-[11px] font-medium leading-none ${item.center ? 'mt-1.5' : ''}`}>{item.label}</span>
            </>
          );
          const cls = `press relative z-10 flex flex-col items-center justify-center gap-1 pt-2.5 pb-2 transition-colors ${
            active ? 'text-green' : 'text-ink-600 active:text-ink-900'
          }`;
          return item.to ? (
            <Link key={item.label} to={item.to} aria-current={active ? 'page' : undefined} className={cls}>
              {inner}
            </Link>
          ) : (
            <button key={item.label} type="button" onClick={item.onClick} className={cls}>
              {inner}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
