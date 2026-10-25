import type { Subscription } from '../api/subscription';

export interface BannerInfo {
  tone: 'coral' | 'amber';
  title: string;
  body: string;
}

const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? '' : 's'}`;
/** Ending soon: warn this many days ahead. */
export const WARN_DAYS = 14;

/** What (if anything) to tell a school's staff about their subscription. The most serious thing wins. */
export function bannerFor(sub: Subscription | null): BannerInfo | null {
  if (!sub) return null;

  if (sub.status === 'SUSPENDED') {
    return { tone: 'coral', title: 'Ledgr is paused for your school', body: 'You can still look at everything, but nothing can be changed until it is switched back on. Contact the Ledgr team.' };
  }
  if (sub.status === 'EXPIRED') {
    return { tone: 'coral', title: 'Your subscription has ended, so Ledgr is read-only', body: 'You can still look at everything. Renew to make changes again. Parents can still pay fees as usual.' };
  }
  if (sub.status === 'GRACE') {
    const left = sub.days_left ?? 0;
    return { tone: 'amber', title: `Your subscription has ended. Renew within ${plural(left, 'day')}`, body: 'After that Ledgr becomes read-only for your staff. Parents can still pay fees as usual.' };
  }
  if (sub.over_limit && sub.learner_limit !== null) {
    return { tone: 'amber', title: `You have ${sub.learner_count} learners, but your plan covers ${sub.learner_limit}`, body: 'Everything keeps working. Contact the Ledgr team to move to a bigger plan.' };
  }
  if ((sub.status === 'TRIAL' || sub.status === 'ACTIVE') && sub.days_left !== null && sub.days_left <= WARN_DAYS) {
    const what = sub.status === 'TRIAL' ? 'Your free trial ends' : 'Your subscription ends';
    return { tone: 'amber', title: `${what} in ${plural(sub.days_left, 'day')}`, body: 'Contact the Ledgr team to keep going without a break.' };
  }
  return null;
}
