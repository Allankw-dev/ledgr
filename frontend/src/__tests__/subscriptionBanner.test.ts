import { describe, expect, it } from 'vitest';
import type { Subscription } from '../api/subscription';
import { bannerFor } from '../components/subscriptionBanner';

const sub = (over: Partial<Subscription> = {}): Subscription => ({
  status: 'ACTIVE', read_only: false, days_left: null, ends_at: null, plan: 'STANDARD', learner_count: 100, learner_limit: null, over_limit: false, ...over,
});

describe('bannerFor', () => {
  it('says nothing while the school is in good standing', () => {
    expect(bannerFor(null)).toBeNull();
    expect(bannerFor(sub())).toBeNull(); // no end date: never expires
    expect(bannerFor(sub({ days_left: 90 }))).toBeNull();
    expect(bannerFor(sub({ status: 'TRIAL', days_left: 25 }))).toBeNull();
  });

  it('warns two weeks ahead, and says whether it is a trial', () => {
    expect(bannerFor(sub({ days_left: 14 }))?.title).toBe('Your subscription ends in 14 days');
    expect(bannerFor(sub({ days_left: 1 }))?.title).toBe('Your subscription ends in 1 day');
    expect(bannerFor(sub({ status: 'TRIAL', days_left: 3 }))?.title).toBe('Your free trial ends in 3 days');
  });

  it('counts down the grace period and promises parents can still pay', () => {
    const b = bannerFor(sub({ status: 'GRACE', days_left: 5 }))!;
    expect(b.tone).toBe('amber');
    expect(b.title).toBe('Your subscription has ended. Renew within 5 days');
    expect(b.body).toMatch(/Parents can still pay/);
  });

  it('is firm once read-only, in the right words for expired vs switched off', () => {
    const expired = bannerFor(sub({ status: 'EXPIRED', read_only: true, days_left: 0 }))!;
    expect(expired.tone).toBe('coral');
    expect(expired.title).toMatch(/read-only/);
    expect(expired.body).toMatch(/Parents can still pay/);
    expect(bannerFor(sub({ status: 'SUSPENDED', read_only: true }))!.title).toBe('Ledgr is paused for your school');
  });

  it('mentions going over the learner limit, but a more serious problem wins', () => {
    const over = sub({ learner_count: 520, learner_limit: 500, over_limit: true });
    expect(bannerFor(over)!.title).toBe('You have 520 learners, but your plan covers 500');
    expect(bannerFor({ ...over, status: 'GRACE', days_left: 2 })!.title).toMatch(/Renew within 2 days/);
  });
});
