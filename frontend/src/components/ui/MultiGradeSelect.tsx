import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';

interface GradeOption {
  id: string;
  name: string;
}

interface MultiGradeSelectProps {
  classes: GradeOption[];
  /** Selected grade ids. Empty = "everything" (whole school / all grades). */
  value: string[];
  onChange: (ids: string[]) => void;
  label?: string;
  /** What "nothing selected" means, e.g. "Whole school" or "All grades". */
  allLabel?: string;
  /** chips = tap-to-toggle grade chips (forms); dropdown = compact checklist popover (filters). */
  variant?: 'chips' | 'dropdown';
}

function summary(classes: GradeOption[], value: string[], allLabel: string) {
  if (value.length === 0) return allLabel;
  const names = classes.filter((c) => value.includes(c.id)).map((c) => c.name);
  if (names.length <= 2) return names.join(', ');
  return `${names.length} grades`;
}

/**
 * Pick one, several, or all grades. Leaving it empty means "everything", which
 * keeps the old "all classes" behaviour; selecting grades narrows it down.
 */
export function MultiGradeSelect({ classes, value, onChange, label, allLabel = 'All grades', variant = 'chips' }: MultiGradeSelectProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const toggle = (id: string) => onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);
  const allSelected = classes.length > 0 && value.length === classes.length;

  if (variant === 'dropdown') {
    return (
      <div className="relative" ref={ref}>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-haspopup="listbox"
          aria-expanded={open}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-ink-200 bg-panel text-ink-900 text-sm focus-visible:outline-2 focus-visible:outline-ink-600 min-w-[9.5rem] justify-between"
        >
          <span className="truncate max-w-[12rem]">{summary(classes, value, allLabel)}</span>
          <ChevronDown className="w-4 h-4 text-ink-400 shrink-0" strokeWidth={2} />
        </button>
        {open && (
          <div className="absolute right-0 mt-1.5 z-30 w-60 rounded-lg border border-ink-200 bg-panel shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 border-b border-ink-200 text-xs">
              <button type="button" onClick={() => onChange(classes.map((c) => c.id))} className="text-emerald-700 hover:underline">
                Select all
              </button>
              <button type="button" onClick={() => onChange([])} className="text-ink-600 hover:underline">
                Clear ({allLabel.toLowerCase()})
              </button>
            </div>
            <div className="max-h-64 overflow-y-auto py-1" role="listbox" aria-multiselectable="true">
              {classes.map((c) => {
                const on = value.includes(c.id);
                return (
                  <button
                    key={c.id}
                    type="button"
                    role="option"
                    aria-selected={on}
                    onClick={() => toggle(c.id)}
                    className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-ink-900 hover:bg-ink-100 text-left"
                  >
                    <span
                      className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${
                        on ? 'bg-emerald-700 border-emerald-700' : 'border-ink-400'
                      }`}
                    >
                      {on && <Check className="w-3 h-3 text-[#06110B]" strokeWidth={3.5} />}
                    </span>
                    {c.name}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {label && <span className="text-sm font-medium text-ink-700">{label}</span>}
      <div className="flex flex-wrap gap-2" role="group" aria-label={label ?? 'Grades'}>
        <button
          type="button"
          onClick={() => onChange([])}
          aria-pressed={value.length === 0}
          className={`px-3.5 py-1.5 rounded-full text-sm border transition-colors ${
            value.length === 0
              ? 'bg-emerald-100 border-emerald-700 text-emerald-700 font-medium'
              : 'border-ink-200 text-ink-600 hover:border-ink-400'
          }`}
        >
          {allLabel}
        </button>
        {classes.map((c) => {
          const on = value.includes(c.id);
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => toggle(c.id)}
              aria-pressed={on}
              className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-sm border transition-colors ${
                on
                  ? 'bg-emerald-100 border-emerald-700 text-emerald-700 font-medium'
                  : 'border-ink-200 text-ink-600 hover:border-ink-400'
              }`}
            >
              {on && <Check className="w-3.5 h-3.5" strokeWidth={3} />}
              {c.name}
            </button>
          );
        })}
      </div>
      <div className="flex items-center justify-between text-xs text-ink-400">
        <span>
          {value.length === 0 ? `${allLabel} — tap grades to narrow it down.` : `${value.length} of ${classes.length} grades selected`}
        </span>
        {classes.length > 1 && (
          <button type="button" onClick={() => onChange(allSelected ? [] : classes.map((c) => c.id))} className="text-emerald-700 hover:underline">
            {allSelected ? 'Clear' : 'Select all grades'}
          </button>
        )}
      </div>
    </div>
  );
}
