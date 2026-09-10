import { useEffect, useState } from 'react';
import { Zap, Play } from 'lucide-react';
import { getAutomationSettings, updateAutomationSettings, runAutomationNow, type SweepResult } from '../api/automation';

export function AutomationCard() {
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [lastResult, setLastResult] = useState<SweepResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAutomationSettings()
      .then((s) => setEnabled(s.enabled))
      .catch(() => setError('Could not load automation settings.'))
      .finally(() => setLoading(false));
  }, []);

  async function handleToggle() {
    const next = !enabled;
    setSaving(true);
    setError(null);
    try {
      const result = await updateAutomationSettings(next);
      setEnabled(result.enabled);
    } catch {
      setError('Could not update the setting. Only school admins can change this.');
    } finally {
      setSaving(false);
    }
  }

  async function handleRunNow() {
    setRunning(true);
    setError(null);
    setLastResult(null);
    try {
      const result = await runAutomationNow();
      setLastResult(result);
    } catch {
      setError('Could not run the sweep. Try again in a moment.');
    } finally {
      setRunning(false);
    }
  }

  if (loading) return null;

  return (
    <div className="bg-panel border border-ink-200 rounded-lg p-5">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <Zap className="w-4 h-4 text-ink-600 mt-0.5" strokeWidth={2} />
          <div>
            <h2 className="font-display text-base text-ink-900 font-medium">Automatic overdue reminders</h2>
            <p className="text-xs text-ink-600 mt-0.5 max-w-md">
              When on, overdue invoices get an escalating reminder automatically — day 1, day 7, and a final notice
              at day 14 — without anyone needing to click "Remind" per invoice.
            </p>
          </div>
        </div>
        <button
          onClick={handleToggle}
          disabled={saving}
          role="switch"
          aria-checked={enabled}
          aria-label="Toggle automatic overdue reminders"
          className={`shrink-0 w-11 h-6 rounded-full transition-colors relative disabled:opacity-60 ${
            enabled ? 'bg-emerald-700' : 'bg-ink-200'
          }`}
        >
          <span
            className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
              enabled ? 'translate-x-5' : ''
            }`}
          />
        </button>
      </div>

      {enabled && (
        <div className="mt-4 pt-4 border-t border-ink-100 flex items-center justify-between">
          <button
            onClick={handleRunNow}
            disabled={running}
            className="text-xs font-medium text-ink-900 hover:underline underline-offset-2 flex items-center gap-1 disabled:opacity-60 disabled:no-underline"
          >
            <Play className="w-3.5 h-3.5" /> {running ? 'Running…' : 'Run now instead of waiting'}
          </button>
          {lastResult && (
            <span className="text-xs text-ink-600">
              Checked {lastResult.invoices_checked}, sent {lastResult.reminders_sent}
            </span>
          )}
        </div>
      )}

      {error && <p className="text-xs text-clay-700 mt-3">{error}</p>}
    </div>
  );
}
