import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { PageMeta } from '../types';

interface PaginationControlsProps {
  meta: PageMeta;
  onPageChange: (page: number) => void;
}

export function PaginationControls({ meta, onPageChange }: PaginationControlsProps) {
  if (meta.total <= meta.page_size) return null;

  const start = (meta.page - 1) * meta.page_size + 1;
  const end = Math.min(meta.page * meta.page_size, meta.total);

  return (
    <div className="px-5 py-3 border-t border-ink-200 flex items-center justify-between text-xs text-ink-600">
      <span>
        {start}–{end} of {meta.total}
      </span>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(meta.page - 1)}
          disabled={meta.page <= 1}
          className="p-1.5 rounded-md border border-ink-200 hover:bg-ink-100 disabled:opacity-40 disabled:cursor-not-allowed"
          aria-label="Previous page"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => onPageChange(meta.page + 1)}
          disabled={!meta.has_more}
          className="p-1.5 rounded-md border border-ink-200 hover:bg-ink-100 disabled:opacity-40 disabled:cursor-not-allowed"
          aria-label="Next page"
        >
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
