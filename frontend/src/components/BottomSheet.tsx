import { useEffect, type ReactNode } from 'react';

/** Slide-up sheet for phone menus. Closes on backdrop tap or Escape. */
export function BottomSheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title?: string; children: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="md:hidden fixed inset-0 z-50 flex items-end">
      <div className="modal-backdrop-in absolute inset-0 bg-ink-950/60" onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="sheet-in relative w-full rounded-t-3xl border border-white/10 border-b-0 bg-panel px-5 pt-3 pb-[max(1.5rem,env(safe-area-inset-bottom))] shadow-[0_-20px_50px_-10px_rgba(0,0,0,0.8)]"
      >
        <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-white/15" aria-hidden="true" />
        {children}
      </div>
    </div>
  );
}
