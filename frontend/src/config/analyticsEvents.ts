import type { BeforeSend, BeforeSendEvent } from '@vercel/analytics/react';

/**
 * Vercel Web Analytics: anonymous page-view counts. It sets no cookies, does not follow people across sites, and
 * stores no names or accounts (Vercel works out "unique visitors" from a daily-rotating hash that cannot be turned
 * back into a person). On top of that, this file makes sure it is never told anything private:
 *
 *  - the query string and #fragment are always removed (links in emails carry one-time tokens there);
 *  - pages that exist only to consume a token are not counted at all;
 *  - ids in the path (a student's or invoice's uuid, or any long number) become ":id";
 *  - nothing is sent if the browser says Do Not Track or Global Privacy Control.
 *
 * Keep the Privacy Policy, Cookie Policy and docs/COMPLIANCE.md in step with this file.
 */

/** Pages whose URL itself is a secret or only exists to act on one: never counted. */
const NOT_COUNTED = ['/reset-password', '/confirm-email', '/unsubscribe', '/verify-child'];

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
const LONG_NUMBER = /\/\d{4,}(?=\/|$)/g;

function browserSaysDoNotTrack(): boolean {
  if (typeof navigator === 'undefined') return false;
  const nav = navigator as Navigator & { globalPrivacyControl?: boolean; msDoNotTrack?: string };
  return nav.doNotTrack === '1' || nav.msDoNotTrack === '1' || nav.globalPrivacyControl === true;
}

/** Exported for tests. Returns the cleaned event, or null to drop it. */
export const cleanAnalyticsEvent: BeforeSend = (event: BeforeSendEvent) => {
  if (browserSaysDoNotTrack()) return null;
  let url: URL;
  try {
    url = new URL(event.url, window.location.origin);
  } catch {
    return null;
  }
  if (NOT_COUNTED.some((p) => url.pathname === p || url.pathname.startsWith(`${p}/`))) return null;
  const path = url.pathname.replace(UUID, ':id').replace(LONG_NUMBER, '/:id');
  return { ...event, url: `${url.origin}${path}` };
};
