import type { InvoiceStatus } from '../../types';

const statusStyles: Record<InvoiceStatus, string> = {
  PAID: 'bg-emerald-100 text-emerald-700',
  PARTIALLY_PAID: 'bg-amber-100 text-amber-700',
  ISSUED: 'bg-ink-100 text-ink-700',
  OVERDUE: 'bg-clay-100 text-clay-700',
  DRAFT: 'bg-ink-100 text-ink-400',
  CANCELLED: 'bg-ink-100 text-ink-400',
};

const statusLabels: Record<InvoiceStatus, string> = {
  PAID: 'Paid',
  PARTIALLY_PAID: 'Partially paid',
  ISSUED: 'Issued',
  OVERDUE: 'Overdue',
  DRAFT: 'Draft',
  CANCELLED: 'Cancelled',
};

export function StatusBadge({ status }: { status: InvoiceStatus }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${statusStyles[status]}`}>
      {statusLabels[status]}
    </span>
  );
}
