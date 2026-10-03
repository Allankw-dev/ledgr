import { type InputHTMLAttributes, type ReactNode, forwardRef } from 'react';

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  /** Optional icon shown inside the field, on the left. */
  icon?: ReactNode;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  ({ label, error, icon, id, className = '', ...props }, ref) => {
    const fieldId = id || label.toLowerCase().replace(/\s+/g, '-');
    const input = (
      <input
        ref={ref}
        id={fieldId}
        className={`neu-input ${icon ? 'w-full pl-10 pr-3.5' : 'px-3.5'} py-2.5 rounded-md border bg-panel text-ink-900 text-base sm:text-sm placeholder:text-ink-400 focus-visible:outline-2 focus-visible:outline-ink-600 ${
          error ? 'neu-input-error' : ''
        } ${className}`}
        aria-invalid={!!error}
        aria-describedby={error ? `${fieldId}-error` : undefined}
        {...props}
      />
    );
    return (
      <div className="flex flex-col gap-1.5">
        <label htmlFor={fieldId} className="text-sm font-medium text-ink-700">
          {label}
        </label>
        {icon ? (
          <div className="relative focus-within:[&>span]:text-green">
            <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-400 transition-colors [&>svg]:w-4 [&>svg]:h-4">{icon}</span>
            {input}
          </div>
        ) : (
          input
        )}
        {error && (
          <p id={`${fieldId}-error`} className="text-sm text-clay-700">
            {error}
          </p>
        )}
      </div>
    );
  }
);
TextField.displayName = 'TextField';
