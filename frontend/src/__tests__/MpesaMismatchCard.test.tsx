import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MpesaMismatchCard } from '../components/MpesaMismatchCard';
import {
  acceptMpesaMismatch,
  dismissMpesaMismatch,
  getMpesaMismatches,
  type MpesaMismatch,
} from '../api/payments';

vi.mock('../api/payments', () => ({
  getMpesaMismatches: vi.fn(),
  acceptMpesaMismatch: vi.fn(),
  dismissMpesaMismatch: vi.fn(),
}));

const item = (over: Partial<MpesaMismatch> = {}): MpesaMismatch => ({
  id: 'p1',
  student_id: 's1',
  student_name: 'Alex Karimi',
  admission_number: '1001',
  expected_amount: '3000.00',
  reported_amount: '2999.00',
  mpesa_receipt: 'RCPMM1',
  created_at: '2026-10-25T09:00:00Z',
  ...over,
});

// Intl puts a non-breaking space between "Ksh" and the number; compare with normal spaces.
const text = () => (document.body.textContent ?? '').replace(/\u00a0/g, ' ');

beforeEach(() => {
  vi.mocked(acceptMpesaMismatch).mockResolvedValue({});
  vi.mocked(dismissMpesaMismatch).mockResolvedValue({});
});

describe('MpesaMismatchCard', () => {
  it('renders nothing when there is nothing to decide', async () => {
    vi.mocked(getMpesaMismatches).mockResolvedValue([]);
    const { container } = render(<MpesaMismatchCard />);
    await waitFor(() => expect(getMpesaMismatches).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });

  it('never breaks the dashboard if the check fails', async () => {
    vi.mocked(getMpesaMismatches).mockRejectedValue(new Error('network'));
    const { container } = render(<MpesaMismatchCard />);
    await waitFor(() => expect(getMpesaMismatches).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });

  it('shows both amounts and the M-Pesa code', async () => {
    vi.mocked(getMpesaMismatches).mockResolvedValue([item()]);
    render(<MpesaMismatchCard />);
    await screen.findByText('Alex Karimi');
    expect(text()).toContain('3,000');
    expect(text()).toContain('2,999');
    expect(text()).toContain('RCPMM1');
  });

  it('records the reported amount, then reloads the list', async () => {
    vi.mocked(getMpesaMismatches).mockResolvedValueOnce([item()]).mockResolvedValue([]);
    const { container } = render(<MpesaMismatchCard />);
    fireEvent.click(await screen.findByRole('button', { name: /Record/ }));
    await waitFor(() => expect(acceptMpesaMismatch).toHaveBeenCalledWith('p1'));
    await waitFor(() => expect(container.textContent).toBe(''));
  });

  it('will not dismiss without a reason', async () => {
    vi.mocked(getMpesaMismatches).mockResolvedValue([item()]);
    render(<MpesaMismatchCard />);
    fireEvent.click(await screen.findByRole('button', { name: 'Dismiss' }));
    const confirm = screen.getByRole('button', { name: 'Dismiss payment' }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Safaricom reversed it' } });
    expect(confirm.disabled).toBe(false);
    fireEvent.click(confirm);
    await waitFor(() => expect(dismissMpesaMismatch).toHaveBeenCalledWith('p1', 'Safaricom reversed it'));
  });

  it('shows the server error and keeps the row when recording fails', async () => {
    vi.mocked(getMpesaMismatches).mockResolvedValue([item()]);
    vi.mocked(acceptMpesaMismatch).mockRejectedValue(new Error('This payment is not waiting on an amount decision'));
    render(<MpesaMismatchCard />);
    fireEvent.click(await screen.findByRole('button', { name: /Record/ }));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('not waiting on an amount decision');
    expect(screen.queryByText('Alex Karimi')).not.toBeNull();
  });
});
