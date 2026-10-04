import { describe, expect, it } from 'vitest';
import { groupReceiptRows } from '../lib/receiptGroups';
import { makeChild } from '../test/fixtures';

describe('groupReceiptRows', () => {
  it('shows one M-Pesa payment split over two invoices as ONE receipt with a breakdown', () => {
    const alex = makeChild('a', 'Alex', [
      { due_date: '2026-10-31T00:00:00Z', payments: [{ id: 'p1', amount: 56010, reference_code: 'RCP1' }] },
      { due_date: '2027-03-29T00:00:00Z', payments: [{ id: 'p2', amount: 3990, reference_code: 'RCP1' }] },
    ]);
    const [group, ...rest] = groupReceiptRows([alex], null);
    expect(rest).toEqual([]);
    expect(group.total).toBe(60000);
    expect(group.slices.map((s) => s.paymentId)).toEqual(['p1', 'p2']); // each keeps its own receipt
    expect(group.slices[0].invoiceLabel).toBe('Invoice due 31 Oct 2026');
  });

  it('never merges cash/bank payments, which have no shared code', () => {
    const alex = makeChild('a', 'Alex', [
      { payments: [{ id: 'c1', amount: 500, method: 'CASH' }, { id: 'c2', amount: 500, method: 'CASH' }] },
    ]);
    expect(groupReceiptRows([alex], null)).toHaveLength(2);
  });

  it('does not merge two different children even if a code collides', () => {
    const a = makeChild('a', 'Alex', [{ payments: [{ id: 'p1', amount: 100, reference_code: 'SAME' }] }]);
    const b = makeChild('b', 'Brian', [{ payments: [{ id: 'p2', amount: 100, reference_code: 'SAME' }] }]);
    expect(groupReceiptRows([a, b], null)).toHaveLength(2);
  });

  it('filters by child and lists the most recent payment first', () => {
    const a = makeChild('a', 'Alex', [
      { payments: [{ id: 'old', amount: 1, reference_code: 'R1', paid_at: '2026-01-01T00:00:00Z' }] },
      { payments: [{ id: 'new', amount: 2, reference_code: 'R2', paid_at: '2026-09-01T00:00:00Z' }] },
    ]);
    const b = makeChild('b', 'Brian', [{ payments: [{ id: 'other', amount: 3, reference_code: 'R3' }] }]);
    expect(groupReceiptRows([a, b], 'a').map((g) => g.slices[0].paymentId)).toEqual(['new', 'old']);
    expect(groupReceiptRows([a, b], 'b').map((g) => g.childName)).toEqual(['Brian']);
  });
});
