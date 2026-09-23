import { type InputHTMLAttributes, forwardRef } from 'react';

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  ({ label, error, id, className = '', ...props }, ref) => {
    const fieldId = id || label.toLowerCase().replace(/\s+/g, '-');
    return (
      <div className="flex flex-col gap-1.5">
        <label htmlFor={fieldId} className="text-sm font-medium text-ink-700">
          {label}
        </label>
        <input
          ref={ref}
          id={fieldId}
          className={`neu-input px-3.5 py-2.5 rounded-md border bg-panel text-ink-900 text-sm placeholder:text-ink-400 focus-visible:outline-2 focus-visible:outline-ink-600 ${
            error ? 'neu-input-error' : ''
          } ${className}`}
          aria-invalid={!!error}
          aria-describedby={error ? `${fieldId}-error` : undefined}
          {...props}
        />
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
