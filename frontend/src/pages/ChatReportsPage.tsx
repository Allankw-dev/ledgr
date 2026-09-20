import { useCallback, useEffect, useState } from 'react';
import { Flag, X } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { getChatReport, listChatReports, updateChatReport } from '../api/direct';
import { getErrorMessage } from '../api/client';
import type { ChatReportDetail, ChatReportSummary, ReportCategory, ReportStatus } from '../types';

const CATEGORY_LABEL: Record<ReportCategory, string> = {
  HARASSMENT: 'Harassment or bullying',
  INAPPROPRIATE: 'Inappropriate content',
  SAFETY_CONCERN: 'Safety concern',
  SPAM: 'Spam',
  OTHER: 'Other',
};

const STATUS_STYLE: Record<ReportStatus, string> = {
  OPEN: 'bg-amber/15 text-amber border-amber/40',
  REVIEWING: 'bg-cyan/10 text-cyan border-cyan/30',
  RESOLVED: 'bg-emerald-100 text-emerald-700 border-emerald-700/30',
  DISMISSED: 'bg-ink-100 text-ink-600 border-ink-200',
};

const FILTERS: { label: string; value: ReportStatus | undefined }[] = [
  { label: 'Open', value: 'OPEN' },
  { label: 'Reviewing', value: 'REVIEWING' },
  { label: 'Closed', value: undefined },
];

function when(iso: string) {
  return new Date(iso).toLocaleString('en-KE', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
}

/** School admin only: review chats that a teacher or parent has reported. */
export function ChatReportsPage() {
  const [filterIdx, setFilterIdx] = useState(0);
  const [reports, setReports] = useState<ChatReportSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<ChatReportDetail | null>(null);
  const [status, setStatus] = useState<ReportStatus>('REVIEWING');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const all = await listChatReports(FILTERS[filterIdx].value);
      // "Closed" shows resolved + dismissed only.
      setReports(filterIdx === 2 ? all.filter((r) => r.status === 'RESOLVED' || r.status === 'DISMISSED') : all);
    } catch (e) {
      setError(getErrorMessage(e, 'Could not load reports.'));
    }
  }, [filterIdx]);

  useEffect(() => {
    void load();
  }, [load]);

  async function openReport(id: string) {
    try {
      const d = await getChatReport(id);
      setOpen(d);
      setStatus(d.status === 'OPEN' ? 'REVIEWING' : d.status);
      setNote(d.resolution_note ?? '');
    } catch (e) {
      setError(getErrorMessage(e, 'Could not open that report.'));
    }
  }

  async function save() {
    if (!open) return;
    setSaving(true);
    try {
      await updateChatReport(open.id, status, note.trim());
      setOpen(null);
      await load();
    } catch (e) {
      setError(getErrorMessage(e, 'Could not save.'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-4 sm:px-8 py-6 sm:py-8">
        <div className="mb-6">
          <h1 className="font-display text-2xl text-ink-900 font-medium flex items-center gap-2">
            <Flag className="w-5 h-5" strokeWidth={1.75} /> Chat reports
          </h1>
          <p className="text-sm text-ink-600 mt-1">
            Private teacher–parent chats that someone has reported. You only see the last 30 messages at the time of the report — never the rest of the chat.
            Every time you open or update a report it’s recorded in the audit log.
          </p>
        </div>

        <div className="flex gap-2 mb-4">
          {FILTERS.map((f, i) => (
            <button
              key={f.label}
              onClick={() => setFilterIdx(i)}
              className={`px-3.5 py-1.5 rounded-full text-sm border ${i === filterIdx ? 'bg-emerald-100 border-emerald-700 text-emerald-700 font-medium' : 'border-ink-200 text-ink-600 hover:border-ink-400'}`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {error && <p role="alert" className="text-sm text-clay-700 bg-clay-100 rounded-md px-3 py-2 mb-4">{error}</p>}

        <div className="bg-panel border border-ink-200 rounded-lg overflow-hidden">
          {reports === null ? (
            <p className="p-6 text-sm text-ink-600">Loading…</p>
          ) : reports.length === 0 ? (
            <p className="p-8 text-sm text-ink-600 text-center">Nothing here — no reports in this list.</p>
          ) : (
            reports.map((r) => (
              <button key={r.id} onClick={() => void openReport(r.id)} className="w-full text-left px-5 py-4 border-b border-ink-100 last:border-0 hover:bg-ink-100/60 flex items-center gap-4">
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-ink-900">
                    <span className="font-medium">{r.reporter.name}</span> reported <span className="font-medium">{r.reported.name}</span>
                  </p>
                  <p className="text-xs text-ink-400 mt-0.5">
                    {CATEGORY_LABEL[r.category]} · {when(r.created_at)}
                  </p>
                </div>
                <span className={`text-[11px] font-medium border rounded-full px-2.5 py-1 shrink-0 ${STATUS_STYLE[r.status]}`}>{r.status}</span>
              </button>
            ))
          )}
        </div>
      </div>

      {open && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-ink-950/60" onClick={() => setOpen(null)}>
          <div className="w-full max-w-2xl rounded-xl border border-ink-200 bg-panel shadow-2xl max-h-[90vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-3 border-b border-ink-200">
              <div>
                <p className="text-sm font-medium text-ink-900">
                  {open.reporter.name} → {open.reported.name}
                </p>
                <p className="text-xs text-ink-400">{CATEGORY_LABEL[open.category]} · {when(open.created_at)}</p>
              </div>
              <button onClick={() => setOpen(null)} aria-label="Close" className="text-ink-400 hover:text-ink-900">
                <X className="w-5 h-5" strokeWidth={2} />
              </button>
            </div>

            <div className="overflow-y-auto px-5 py-4 flex flex-col gap-4">
              {open.details && (
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-ink-400 mb-1">What {open.reporter.name.split(' ')[0]} said</p>
                  <p className="text-sm text-ink-900 bg-ink-100 border border-ink-200 rounded-md px-3 py-2 whitespace-pre-wrap">{open.details}</p>
                </div>
              )}

              <div>
                <p className="text-[11px] uppercase tracking-wide text-ink-400 mb-1">Messages at the time of the report</p>
                <div className="flex flex-col gap-1.5 chat-wallpaper rounded-lg p-3 max-h-72 overflow-y-auto">
                  {open.evidence.map((e, i) => (
                    <div key={i} className={`max-w-[85%] rounded-xl px-3 py-2 text-sm border ${e.sender_is_reported ? 'self-start bg-clay-100 border-clay-700/30' : 'self-end bg-ink-100 border-ink-200'} text-ink-900`}>
                      <p className="text-[11px] font-semibold text-ink-600">
                        {e.sender_name} {e.sender_is_reported && <span className="text-clay-700">(reported)</span>}
                      </p>
                      {e.deleted_before_report ? (
                        <p className="italic text-ink-400">Deleted before the report was filed</p>
                      ) : (
                        <>
                          {e.attachment_name && <p className="text-xs text-violet">📎 {e.attachment_name}</p>}
                          {e.body && <p className="whitespace-pre-wrap break-words">{e.body}</p>}
                        </>
                      )}
                      <p className="text-[10px] text-ink-400 text-right mt-0.5">{when(e.sent_at)}</p>
                    </div>
                  ))}
                </div>
                <p className="text-[11px] text-ink-400 mt-1">Attached files aren’t included in a report — only their names.</p>
              </div>

              <div className="grid gap-3">
                <label className="flex flex-col gap-1.5 text-sm font-medium text-ink-700">
                  Status
                  <select value={status} onChange={(e) => setStatus(e.target.value as ReportStatus)} className="px-3 py-2 rounded-md border border-ink-200 bg-panel text-ink-900 text-sm font-normal">
                    <option value="REVIEWING">Reviewing</option>
                    <option value="RESOLVED">Resolved</option>
                    <option value="DISMISSED">Dismissed</option>
                    <option value="OPEN">Open</option>
                  </select>
                </label>
                <label className="flex flex-col gap-1.5 text-sm font-medium text-ink-700">
                  Your note (only school admins can see this)
                  <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={2000} className="px-3.5 py-2.5 rounded-md border border-ink-200 bg-panel text-ink-900 text-sm font-normal resize-y" />
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 px-5 py-3 border-t border-ink-200">
              <button onClick={() => setOpen(null)} className="px-4 py-2 rounded-md border border-ink-200 text-sm text-ink-900 hover:bg-ink-100">Close</button>
              <button onClick={() => void save()} disabled={saving} className="px-4 py-2 rounded-md bg-emerald-700 text-[#06110B] text-sm font-medium disabled:opacity-50">
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
