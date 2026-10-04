import type { ParentStudentView } from '../types';

export interface PaymentFixture {
  id: string;
  amount: number;
  reference_code?: string | null;
  method?: string;
  paid_at?: string;
}

export interface InvoiceFixture {
  due_date?: string;
  total?: number;
  paid?: number;
  status?: string;
  payments?: PaymentFixture[];
}

/** A parent's child with just the fields the screens read. */
export function makeChild(id: string, fullName: string, invoices: InvoiceFixture[] = []): ParentStudentView {
  return {
    id,
    full_name: fullName,
    admission_number: id.toUpperCase(),
    class_name: 'Grade 4',
    balance_due: '0',
    invoices: invoices.map((inv, i) => ({
      id: `${id}-inv-${i}`,
      due_date: inv.due_date ?? '2026-10-31T00:00:00Z',
      total_amount: String(inv.total ?? 1000),
      amount_paid: String(inv.paid ?? 0),
      status: inv.status ?? 'ISSUED',
      items: [],
      payments: (inv.payments ?? []).map((p) => ({
        id: p.id,
        amount: String(p.amount),
        method: p.method ?? 'MPESA',
        paid_at: p.paid_at ?? '2026-10-04T10:00:00Z',
        reference_code: p.reference_code ?? null,
      })),
    })),
  } as unknown as ParentStudentView;
}
