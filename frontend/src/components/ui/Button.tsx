import { type ButtonHTMLAttributes, type ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  children: ReactNode;
}

// primary/danger use dedicated classes that combine the neumorphic raised
// depth with their colored glow in one box-shadow (see index.css — a
// separate .neu-raised class would lose that fight to Tailwind's own
// shadow-[...] utility). secondary has no competing shadow, so it can use
// the shared .neu-raised utility directly. ghost stays flat on purpose:
// it's the lowest-emphasis action, and giving it the same depth as
// everything else would blur that hierarchy rather than support it.
const variantStyles: Record<string, string> = {
  primary: 'btn-neu-primary bg-gradient-to-br from-emerald-700 to-cyan text-[#06110B] disabled:opacity-50',
  secondary: 'neu-raised bg-panel text-ink-900 border border-ink-200 hover:bg-ink-100',
  ghost: 'text-ink-700 hover:bg-ink-100 transition-colors',
  danger: 'btn-neu-danger bg-clay-600 text-white hover:bg-clay-700',
};

export function Button({ variant = 'primary', className = '', children, ...props }: ButtonProps) {
  return (
    <button
      className={`px-4 py-2.5 rounded-md font-medium text-sm disabled:cursor-not-allowed disabled:opacity-60 ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
