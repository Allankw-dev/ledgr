import { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { apiClient } from '../api/client';

interface RiskAssessment {
  score: number;
  level: 'low' | 'medium' | 'high';
  explanation: string;
}

const levelStyles: Record<string, string> = {
  low: 'bg-emerald-100 text-emerald-700',
  medium: 'bg-amber-100 text-amber-700',
  high: 'bg-clay-100 text-clay-700',
};

const levelLabels: Record<string, string> = {
  low: 'Low risk',
  medium: 'Medium risk',
  high: 'High risk',
};

export function RiskBadge({ invoiceId }: { invoiceId: string }) {
  const [risk, setRisk] = useState<RiskAssessment | null>(null);
  const [showTooltip, setShowTooltip] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  async function loadRisk() {
    if (loaded || loading) return;
    setLoading(true);
    try {
      const { data } = await apiClient.get<RiskAssessment>(`/api/invoices/${invoiceId}/risk`);
      setRisk(data);
      setLoaded(true);
    } catch {
      // Silently skip — risk scoring is an enhancement, not core functionality
    } finally {
      setLoading(false);
    }
  }

  if (!loaded && !loading) {
    // Lazy-load on hover/focus rather than for every row on page load —
    // this endpoint does real computation per invoice, so firing it for
    // every row in a long list upfront would be wasteful.
    return (
      <button
        onMouseEnter={loadRisk}
        onFocus={loadRisk}
        className="text-xs text-ink-400 hover:text-ink-600 underline underline-offset-2"
      >
        Check risk
      </button>
    );
  }

  if (loading || !risk) {
    return <span className="text-xs text-ink-400">…</span>;
  }

  return (
    <div className="relative inline-block">
      <button
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onFocus={() => setShowTooltip(true)}
        onBlur={() => setShowTooltip(false)}
        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${levelStyles[risk.level]}`}
      >
        {risk.level === 'high' && <AlertTriangle className="w-3 h-3" />}
        {levelLabels[risk.level]}
      </button>
      {showTooltip && (
        <div
          role="tooltip"
          className="absolute z-10 top-full left-0 mt-1.5 w-56 bg-ink-900 text-white text-xs rounded-md px-3 py-2 shadow-lg"
        >
          {risk.explanation}
        </div>
      )}
    </div>
  );
}
