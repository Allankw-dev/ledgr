import { useEffect, useState } from 'react';
import { ScrollText } from 'lucide-react';
import { AppShell } from '../components/AppShell';
import { SelectField } from '../components/ui/SelectField';
import { PaginationControls } from '../components/ui/PaginationControls';
import { listAuditLogs, listAuditActions, type AuditLogEntry } from '../api/auditLogs';
import type { PageMeta } from '../types';

function humanizeAction(action: string): string {
  return action
    .toLowerCase()
    .split('_')
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(' ');
}

function formatMetadata(metadata: Record<string, unknown> | null): string {
  if (!metadata) return '';
  return Object.entries(metadata)
    .map(([k, v]) => `${k}: ${v}`)
    .join(' · ');
}

export function AuditLogPage() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [meta, setMeta] = useState<PageMeta | null>(null);
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState('');
  const [availableActions, setAvailableActions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAuditActions()
      .then(setAvailableActions)
      .catch(() => {
        /* filter dropdown just stays empty — not worth surfacing as an error */
      });
  }, []);

  useEffect(() => {
    setPage(1);
  }, [actionFilter]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    listAuditLogs(page, 25, actionFilter || undefined)
      .then((data) => {
        setEntries(data.items);
        setMeta(data.meta);
      })
      .catch(() => setError('Could not load the audit log. Check your connection and try again.'))
      .finally(() => setLoading(false));
  }, [page, actionFilter]);

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto px-8 py-8">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl text-ink-900 font-medium flex items-center gap-2">
              <ScrollText className="w-5 h-5" strokeWidth={1.75} />
              Audit log
            </h1>
            <p className="text-sm text-ink-600 mt-1">Every meaningful change, who made it, and when.</p>
          </div>
          <div className="w-56">
            <SelectField
              label="Filter by action"
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              options={availableActions.map((a) => ({ value: a, label: humanizeAction(a) }))}
              placeholder="All actions"
            />
          </div>
        </div>

        {error && (
          <div role="alert" className="bg-clay-100 text-clay-700 rounded-md px-4 py-3 text-sm mb-6">
            {error}
          </div>
        )}

        <div className="bg-white border border-ink-200 rounded-lg overflow-hidden">
          {loading ? (
            <div className="px-5 py-12 text-center text-sm text-ink-600">Loading…</div>
          ) : entries.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <p className="text-sm text-ink-600">No activity recorded yet.</p>
            </div>
          ) : (
            <div className="divide-y divide-ink-100">
              {entries.map((e) => (
                <div key={e.id} className="px-5 py-3 flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-ink-900">{humanizeAction(e.action)}</span>
                      <span className="text-xs text-ink-400">{e.entity_type}</span>
                    </div>
                    <p className="text-xs text-ink-600 mt-0.5">
                      {e.actor_name}
                      {e.metadata && ` — ${formatMetadata(e.metadata)}`}
                    </p>
                  </div>
                  <span className="text-xs text-ink-400 shrink-0 figure">
                    {new Date(e.created_at).toLocaleString('en-KE', {
                      day: '2-digit',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
              ))}
            </div>
          )}
          {meta && <PaginationControls meta={meta} onPageChange={setPage} />}
        </div>
      </div>
    </AppShell>
  );
}
