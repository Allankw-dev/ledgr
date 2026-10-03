import type { ReactNode } from 'react';
import { Moon, Sun, Sunrise, type LucideIcon } from 'lucide-react';

export interface WelcomeChip {
  icon: LucideIcon;
  label: string;
  /** 'good' = green, 'warn' = amber, default = neutral. */
  tone?: 'good' | 'warn';
}

function greetingFor(hour: number): { text: string; Icon: LucideIcon } {
  if (hour < 12) return { text: 'Good morning', Icon: Sunrise };
  if (hour < 17) return { text: 'Good afternoon', Icon: Sun };
  return { text: 'Good evening', Icon: Moon };
}

const toneClass = {
  good: 'text-green bg-green/10 ring-green/25',
  warn: 'text-amber bg-amber/10 ring-amber/25',
  neutral: 'text-ink-700 bg-white/[0.06] ring-white/10',
};

/**
 * The hero at the top of the parent and admin dashboards: a time-aware
 * greeting, the person's name in large type next to a softly spinning
 * gradient avatar, today's date, and a row of quick facts.
 */
export function WelcomeBanner({
  fullName,
  role,
  subtitle,
  chips = [],
  action,
}: {
  fullName?: string | null;
  role: string;
  subtitle: string;
  chips?: WelcomeChip[];
  action?: ReactNode;
}) {
  const now = new Date();
  const { text, Icon } = greetingFor(now.getHours());
  const rawFirst = fullName?.trim().split(/\s+/)[0] ?? '';
  const first = rawFirst ? rawFirst.charAt(0).toUpperCase() + rawFirst.slice(1) : '';
  const initial = first.charAt(0) || '•';
  const dateLabel = new Intl.DateTimeFormat('en-KE', { weekday: 'long', day: 'numeric', month: 'long' }).format(now);

  return (
    <section className="welcome-card sheen relative overflow-hidden rounded-3xl border border-white/10 p-5 sm:p-7 mb-6 reveal">
      {/* Decorative arcs, fading toward the left so text stays clean. */}
      <svg className="pointer-events-none absolute -right-10 -top-12 w-72 h-72 sm:w-96 sm:h-96 opacity-60" viewBox="0 0 400 400" fill="none" aria-hidden="true">
        <defs>
          <linearGradient id="wb-arc" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#39FF88" stopOpacity="0.5" />
            <stop offset="1" stopColor="#3FD9FF" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[70, 115, 160, 205].map((r, i) => (
          <circle key={r} cx="300" cy="100" r={r} stroke="url(#wb-arc)" strokeWidth="1.2" strokeDasharray={i % 2 ? '2 7' : undefined} />
        ))}
      </svg>

      <div className="relative flex items-center gap-4 sm:gap-5">
        <div className="avatar-orbit relative shrink-0 w-14 h-14 sm:w-[72px] sm:h-[72px] rounded-full overflow-hidden">
          <span className="avatar-spin absolute -inset-1/2" aria-hidden="true" />
          <span className="absolute inset-[3px] rounded-full bg-gradient-to-br from-[#122033] to-[#0A0C16] flex items-center justify-center font-display text-xl sm:text-3xl font-semibold text-green">
            {initial}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-600">
            <span className="inline-flex items-center gap-1.5 text-green font-medium">
              <Icon className="w-3.5 h-3.5" strokeWidth={2} />
              {text}
            </span>
            <span className="text-ink-400" aria-hidden="true">·</span>
            <span>{dateLabel}</span>
          </p>
          <h1 className="welcome-title mt-1 text-[1.75rem] sm:text-4xl leading-[1.1] truncate">
            {first ? <span className="welcome-name">{first}</span> : <span className="welcome-name">Welcome</span>}
          </h1>
          <p className="mt-1 flex items-center gap-2 text-sm text-ink-600">
            <span className="shrink-0 rounded-full bg-white/[0.07] ring-1 ring-white/10 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-ink-700">{role}</span>
            <span className="truncate hidden sm:inline">{subtitle}</span>
          </p>
        </div>
      </div>

      <p className="relative mt-3 text-sm text-ink-600 sm:hidden">{subtitle}</p>

      {(chips.length > 0 || action) && (
        <div className="relative mt-5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            {chips.map(({ icon: ChipIcon, label, tone }, i) => (
              <span
                key={label}
                className={`pop-in inline-flex items-center gap-1.5 rounded-full ring-1 px-3 py-1.5 text-xs font-medium ${toneClass[tone ?? 'neutral']}`}
                style={{ animationDelay: `${0.25 + i * 0.08}s` }}
              >
                <ChipIcon className="w-3.5 h-3.5" strokeWidth={2} />
                {label}
              </span>
            ))}
          </div>
          {action}
        </div>
      )}
    </section>
  );
}
