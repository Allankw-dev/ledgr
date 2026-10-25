import { AlertTriangle, Lock } from 'lucide-react';
import type { Subscription } from '../api/subscription';
import { bannerFor } from './subscriptionBanner';

export function SubscriptionBanner({ subscription }: { subscription: Subscription | null }) {
  const info = bannerFor(subscription);
  if (!info) return null;
  const coral = info.tone === 'coral';
  const Icon = coral ? Lock : AlertTriangle;
  return (
    <div
      role={coral ? 'alert' : 'status'}
      className={`mx-4 sm:mx-6 xl:mx-8 mt-4 flex items-start gap-3 rounded-xl border px-4 py-3 ${
        coral ? 'bg-coral-100 border-coral/30 text-ink-900' : 'bg-amber-100 border-amber/30 text-ink-900'
      }`}
    >
      <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${coral ? 'text-coral' : 'text-amber'}`} strokeWidth={2} />
      <div className="min-w-0">
        <p className="text-sm font-medium">{info.title}</p>
        <p className="text-xs text-ink-600 mt-0.5">{info.body}</p>
      </div>
    </div>
  );
}
