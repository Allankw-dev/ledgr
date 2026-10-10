import { useNavigate } from 'react-router-dom';
import { Megaphone, Zap } from 'lucide-react';
import { formatKpi, pluralize } from './format';

export function PromoCard({ outstanding, overdueCount }: { outstanding: number; overdueCount: number }) {
  const navigate = useNavigate();
  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-white/[0.06] p-5 sm:p-6 min-h-[240px] flex flex-col"
      style={{ background: 'radial-gradient(120% 90% at 100% 0%, rgba(184,242,75,0.30) 0%, rgba(32,60,18,0.55) 42%, #14170F 100%)' }}
    >
      <span className="self-start inline-flex items-center gap-1.5 rounded-full bg-white/10 ring-1 ring-white/15 px-2.5 py-1 text-[11px] text-ink-900">
        <Zap className="w-3 h-3 text-lime" strokeWidth={2.5} />
        Collections
      </span>
      <p className="figure text-4xl sm:text-[2.6rem] leading-none text-ink-900 mt-5">{formatKpi(outstanding)}</p>
      <p className="text-xs text-ink-600 mt-2">still outstanding</p>
      <p className="text-sm text-ink-700 mt-4 max-w-[30ch]">
        {overdueCount > 0
          ? `${pluralize(overdueCount, 'invoice')} overdue. A quick reminder usually moves them.`
          : 'Nothing is overdue right now. Keep it that way.'}
      </p>
      <div className="mt-auto pt-6 flex items-center gap-3">
        <button
          onClick={() => navigate('/invoices')}
          className="flex-1 rounded-full bg-lime text-[#0B1203] font-semibold text-sm py-3 hover:brightness-95 active:brightness-90 transition"
        >
          Review invoices
        </button>
        <button
          onClick={() => navigate('/announcements')}
          aria-label="Send an announcement"
          className="w-11 h-11 rounded-full bg-white/10 ring-1 ring-white/15 flex items-center justify-center text-ink-900 hover:bg-white/15 transition-colors"
        >
          <Megaphone className="w-4 h-4" strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}
