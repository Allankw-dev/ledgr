import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanAnalyticsEvent } from '../config/analyticsEvents';

const ORIGIN = window.location.origin;
const view = (path: string) => ({ type: 'pageview' as const, url: `${ORIGIN}${path}` });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('analytics only ever sees a cleaned address', () => {
  it('removes the query string and the fragment', () => {
    expect(cleanAnalyticsEvent(view('/students?search=jane&page=2#top'))).toEqual(view('/students'));
  });

  it.each(['/reset-password', '/confirm-email', '/unsubscribe', '/verify-child', '/unsubscribe/x'])(
    'does not count %s at all (its address is or acts on a one-time token)',
    (path) => {
      expect(cleanAnalyticsEvent(view(`${path}?token=abc123`))).toBeNull();
    },
  );

  it('replaces uuids and long numbers in the path with :id', () => {
    expect(cleanAnalyticsEvent(view('/students/3f2b8c1e-9d4a-4e6b-8a1f-0c7d5e2b9a41/invoices'))).toEqual(
      view('/students/:id/invoices'),
    );
    expect(cleanAnalyticsEvent(view('/receipts/20260017'))).toEqual(view('/receipts/:id'));
  });

  it('leaves ordinary pages alone', () => {
    expect(cleanAnalyticsEvent(view('/dashboard'))).toEqual(view('/dashboard'));
    expect(cleanAnalyticsEvent(view('/privacy'))).toEqual(view('/privacy'));
  });

  it('keeps the event type', () => {
    expect(cleanAnalyticsEvent({ type: 'event', url: `${ORIGIN}/dashboard?x=1` })).toEqual({
      type: 'event',
      url: `${ORIGIN}/dashboard`,
    });
  });

  it('sends nothing when the browser says Do Not Track', () => {
    vi.stubGlobal('navigator', { ...navigator, doNotTrack: '1' });
    expect(cleanAnalyticsEvent(view('/dashboard'))).toBeNull();
  });

  it('sends nothing when Global Privacy Control is on', () => {
    vi.stubGlobal('navigator', { ...navigator, globalPrivacyControl: true });
    expect(cleanAnalyticsEvent(view('/dashboard'))).toBeNull();
  });

  it('drops an address it cannot parse', () => {
    expect(cleanAnalyticsEvent({ type: 'pageview', url: 'http://[bad' })).toBeNull();
  });
});
