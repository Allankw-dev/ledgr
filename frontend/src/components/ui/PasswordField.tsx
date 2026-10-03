import { useState, forwardRef, type InputHTMLAttributes, type ReactNode } from 'react';
import { Eye, EyeOff } from 'lucide-react';

interface PasswordFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string;
  error?: string;
  /** Optional icon shown inside the field, on the left. */
  icon?: ReactNode;
}

export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(
  ({ label, error, icon, id, className = '', ...props }, ref) => {
    const [visible, setVisible] = useState(false);
    const fieldId = id || label.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className="flex flex-col gap-1.5">
        <label htmlFor={fieldId} className="text-sm font-medium text-ink-700">
          {label}
        </label>
        <div className={`relative ${icon ? 'focus-within:[&>span]:text-green' : ''}`}>
          {icon && (
            <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-400 transition-colors [&>svg]:w-4 [&>svg]:h-4">{icon}</span>
          )}
          <input
            ref={ref}
            id={fieldId}
            type={visible ? 'text' : 'password'}
            className={`neu-input w-full ${icon ? 'pl-10' : 'pl-3.5'} py-2.5 pr-10 rounded-md border bg-panel text-ink-900 text-base sm:text-sm placeholder:text-ink-400 focus-visible:outline-2 focus-visible:outline-ink-600 ${
              error ? 'neu-input-error' : ''
            } ${className}`}
            aria-invalid={!!error}
            {...props}
          />
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            aria-label={visible ? 'Hide password' : 'Show password'}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-600"
          >
            {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        {error && <p className="text-sm text-clay-700">{error}</p>}
      </div>
    );
  }
);
PasswordField.displayName = 'PasswordField';
