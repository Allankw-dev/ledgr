import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { UnallocatedPaymentsCard } from '../components/UnallocatedPaymentsCard';
import {
  applyUnallocatedPayment,
  getUnallocatedPayments,
  markPaymentRefunded,
  type UnallocatedPayment,
} from '../api/payments';

vi.mock('../api/payments', () => ({
  getUnallocatedPayments: vi.fn(),
  applyUnallocatedPayment: vi.fn(),
  markPaymentRefunded: vi.fn(),
}));

const payment = (over: Partial<UnallocatedPayment> = {}): UnallocatedPayment => ({
  id: 'p1',
  student_id: 's1',
  student_name: 'Alex Karimi',
  admission_number: '1001',
  amount: '500',
  method: 'MPESA',
  reference_code: 'RCPX1',
  paid_at: '2026-10-04T10:00:00Z',
  notes: null,
  open_invoices: [
    { id: 'i1', label: 'Term 2', due_date: '2027-03-29T00:00:00Z', balance: '3000' },
    { id: 'i2', label: 'Term 3', due_date: '2027-07-01T00:00:00Z', balance: '200' },
  ],
  ...over,
});

// Intl puts a non-breaking space between "Ksh" and the number; compare with normal spaces.
const text = () => (document.body.textContent ?? '').replace(/\u00a0/g, ' ');

beforeEach(() => {
  vi.mocked(applyUnallocatedPayment).mockResolvedValue({});
  vi.mocked(markPaymentRefunded).mockResolvedValue({});
});

describe('UnallocatedPaymentsCard', () => {
  it('renders nothing when there is nothing to decide', async () => {
    vi.mocked(getUnallocatedPayments).mockResolvedValue([]);
    const { container } = render(<UnallocatedPaymentsCard />);
    await waitFor(() => expect(getUnallocatedPayments).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });

  it('never breaks the dashboard if the check fails', async () => {
    vi.mocked(getUnallocatedPayments).mockRejectedValue(new Error('network'));
    const { container } = render(<UnallocatedPaymentsCard />);
    await waitFor(() => expect(getUnallocatedPayments).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });

  it('lists who, how much and the M-Pesa code, with a total', async () => {
    vi.mocked(getUnallocatedPayments).mockResolvedValue([payment(), payment({ id: 'p2', student_name: 'Brian', amount: '1500' })]);
    render(<UnallocatedPaymentsCard />);
    await screen.findByText(/2 payments waiting for an invoice/);
    expect(text()).toContain('Ksh 2,000'); // 500 + 1,500
    expect(text()).toContain('Alex Karimi');
    expect(text()).toContain('RCPX1');
  });

  it('applies to the invoice the bursar picked, then reloads the list', async () => {
    vi.mocked(getUnallocatedPayments).mockResolvedValueOnce([payment()]).mockResolvedValueOnce([]);
    const { container } = render(<UnallocatedPaymentsCard />);
    const select = (await screen.findByLabelText('Apply to')) as HTMLSelectElement;
    expect(select.value).toBe('i1'); // oldest open invoice preselected
    fireEvent.change(select, { target: { value: 'i2' } });
    // i2 only owes 200 of the 500, so the button says exactly what will happen
    fireEvent.click(screen.getByRole('button', { name: /Apply Ksh\s200/ }));
    await waitFor(() => expect(applyUnallocatedPayment).toHaveBeenCalledWith('p1', 'i2'));
    await waitFor(() => expect(container.textContent).toBe(''));
  });

  it('explains when the student has no open invoice, and offers only the refund', async () => {
    vi.mocked(getUnallocatedPayments).mockResolvedValue([payment({ open_invoices: [] })]);
    render(<UnallocatedPaymentsCard />);
    await screen.findByText(/no open invoice right now/);
    expect(screen.queryByLabelText('Apply to')).toBeNull();
    expect(screen.getByRole('button', { name: 'Mark refunded' })).toBeTruthy();
  });

  it('asks for confirmation before recording a refund, and passes the note', async () => {
    vi.mocked(getUnallocatedPayments).mockResolvedValueOnce([payment()]).mockResolvedValueOnce([]);
    render(<UnallocatedPaymentsCard />);
    fireEvent.click(await screen.findByRole('button', { name: 'Mark refunded' }));
    expect(markPaymentRefunded).not.toHaveBeenCalled(); // not yet — just the warning
    expect(text()).toContain('does not send money');
    fireEvent.change(screen.getByLabelText('Note (optional)'), { target: { value: 'sent back 5 Oct' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm refund' }));
    await waitFor(() => expect(markPaymentRefunded).toHaveBeenCalledWith('p1', 'sent back 5 Oct'));
  });

  it('shows the server error and keeps the payment on the list when applying fails', async () => {
    vi.mocked(getUnallocatedPayments).mockResolvedValue([payment()]);
    vi.mocked(applyUnallocatedPayment).mockRejectedValue(new Error('That invoice has nothing left to pay'));
    render(<UnallocatedPaymentsCard />);
    fireEvent.click(await screen.findByRole('button', { name: /^Apply/ }));
    await screen.findByText('That invoice has nothing left to pay');
    expect(screen.getByText('Alex Karimi')).toBeTruthy();
  });
});
