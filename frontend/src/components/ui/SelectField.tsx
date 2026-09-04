import { type SelectHTMLAttributes, forwardRef } from 'react';

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  error?: string;
  options: { value: string; label: string }[];
  placeholder?: string;
}

export const SelectField = forwardRef<HTMLSelectElement, SelectFieldProps>(
  ({ label, error, id, options, placeholder, className = '', ...props }, ref) => {
    const fieldId = id || label.toLowerCase().replace(/\s+/g, '-');
    return (
      <div className="flex flex-col gap-1.5">
        <label htmlFor={fieldId} className="text-sm font-medium text-ink-800">
          {label}
        </label>
        <select
          ref={ref}
          id={fieldId}
          className={`px-3.5 py-2.5 rounded-md border bg-white text-ink-900 text-sm focus-visible:outline-2 focus-visible:outline-ink-600 ${
            error ? 'border-clay-600' : 'border-ink-200'
          } ${className}`}
          aria-invalid={!!error}
          {...props}
        >
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {error && <p className="text-sm text-clay-700">{error}</p>}
      </div>
    );
  }
);
SelectField.displayName = 'SelectField';
