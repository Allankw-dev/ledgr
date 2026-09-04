import { type ButtonHTMLAttributes, type ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  children: ReactNode;
}

const variantStyles: Record<string, string> = {
  primary: 'bg-ink-900 text-paper hover:bg-ink-800 disabled:bg-ink-400',
  secondary: 'bg-white text-ink-900 border border-ink-200 hover:bg-ink-100',
  ghost: 'text-ink-700 hover:bg-ink-100',
  danger: 'bg-clay-600 text-white hover:bg-clay-700',
};

export function Button({ variant = 'primary', className = '', children, ...props }: ButtonProps) {
  return (
    <button
      className={`px-4 py-2.5 rounded-md font-medium text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
