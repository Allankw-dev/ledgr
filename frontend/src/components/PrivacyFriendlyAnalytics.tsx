import { Analytics } from '@vercel/analytics/react';
import { cleanAnalyticsEvent } from '../config/analyticsEvents';

/** Vercel Web Analytics with every address cleaned first. What is and is not sent is explained in config/analyticsEvents.ts. */
export function PrivacyFriendlyAnalytics() {
  return <Analytics beforeSend={cleanAnalyticsEvent} />;
}
