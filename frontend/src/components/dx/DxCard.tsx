import type { ReactNode } from 'react';

export function DxCard({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`bg-dx border border-white/[0.06] rounded-2xl ${className}`}>{children}</div>;
}

export function DxCardTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 mb-4">
      <h2 className="font-display text-lg text-ink-900">{children}</h2>
      {action}
    </div>
  );
}
