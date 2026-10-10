import { describe, expect, it } from 'vitest';
import { formatKpi, humanizeAction, initialsOf, pluralize, timeAgo } from '../components/dx/format';

describe('dx format helpers', () => {
  it('shows the full amount while it fits and goes compact from 100k', () => {
    expect(formatKpi(6010)).toMatch(/6,010/);
    expect(formatKpi(99_999)).toMatch(/99,999/);
    expect(formatKpi(1_140_000)).toMatch(/1\.1\s?M/);
    expect(formatKpi(450_000)).toMatch(/450\s?K/);
  });

  it('turns audit action codes into readable words', () => {
    expect(humanizeAction('PAYMENT_RECORDED')).toBe('Payment Recorded');
    expect(humanizeAction('login')).toBe('Login');
  });

  it('describes how long ago something happened', () => {
    const now = new Date('2026-10-10T12:00:00Z').getTime();
    expect(timeAgo('2026-10-10T11:59:40Z', now)).toBe('Just now');
    expect(timeAgo('2026-10-10T11:15:00Z', now)).toBe('45m ago');
    expect(timeAgo('2026-10-10T07:00:00Z', now)).toBe('5h ago');
    expect(timeAgo('2026-10-08T12:00:00Z', now)).toBe('2d ago');
  });

  it('pluralizes and makes initials', () => {
    expect(pluralize(1, 'invoice')).toBe('1 invoice');
    expect(pluralize(3, 'invoice')).toBe('3 invoices');
    expect(initialsOf('Josh Kamau')).toBe('JK');
    expect(initialsOf('  amani  ')).toBe('A');
    expect(initialsOf('')).toBe('?');
  });
});
