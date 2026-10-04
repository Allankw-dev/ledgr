import type { ParentStudentView } from '../types';

export interface ReceiptSlice {
  paymentId: string;
  amount: number;
  /** Which invoice this slice went to, e.g. "Invoice due 31 Oct 2026". */
  invoiceLabel: string;
}

export interface ReceiptGroup {
  key: string;
  childName: string;
  method: string;
  paidAt: string | null;
  reference: string | null;
  total: number;
  slices: ReceiptSlice[];
}

function invoiceLabel(dueDate: string | undefined) {
  if (!dueDate) return 'Invoice';
  return `Invoice due ${new Date(dueDate).toLocaleDateString('en-KE', { day: 'numeric', month: 'short', year: 'numeric' })}`;
}

/**
 * One M-Pesa payment can be applied across several invoices, which is stored as several
 * payment rows sharing the same receipt code. A parent paid ONCE, so those rows are shown
 * as one receipt with a breakdown. Rows with no code (cash, bank) are never merged — we
 * can't know they belong together.
 */
export function groupReceiptRows(children: ParentStudentView[], selectedChildId: string | null): ReceiptGroup[] {
  const groups = new Map<string, ReceiptGroup>();

  for (const child of children) {
    if (selectedChildId && child.id !== selectedChildId) continue;
    for (const inv of child.invoices) {
      for (const p of inv.payments) {
        const key = p.reference_code ? `${child.id}|${p.reference_code}` : `single|${p.id}`;
        const slice: ReceiptSlice = { paymentId: p.id, amount: Number(p.amount), invoiceLabel: invoiceLabel(inv.due_date) };
        const existing = groups.get(key);
        if (existing) {
          existing.slices.push(slice);
          existing.total += slice.amount;
        } else {
          groups.set(key, {
            key,
            childName: child.full_name,
            method: p.method,
            paidAt: p.paid_at,
            reference: p.reference_code ?? null,
            total: slice.amount,
            slices: [slice],
          });
        }
      }
    }
  }

  return [...groups.values()].sort((a, b) => new Date(b.paidAt || 0).getTime() - new Date(a.paidAt || 0).getTime());
}
