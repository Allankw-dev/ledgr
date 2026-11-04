import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PayWithMpesa } from '../components/PayWithMpesa';
import { resetMpesaAvailability } from '../hooks/useMpesaAvailable';
import { useAuthStore } from '../store/authStore';
import { getMpesaStatus } from '../api/mpesa';

vi.mock('../api/parent', () => ({ requestMpesaPayment: vi.fn() }));
vi.mock('../api/mpesa', () => ({ getMpesaStatus: vi.fn(), lookupMpesaTransaction: vi.fn(), matchMpesaTransaction: vi.fn() }));

function signInAt(schoolId: string) {
  act(() => {
    useAuthStore.setState({ token: 't', refreshToken: null, user: { id: 'u1', school_id: schoolId, role: 'PARENT', email: 'p@x.example', full_name: 'P' } as never });
  });
}

const buttons = (n: number) =>
  render(
    <>
      {Array.from({ length: n }, (_, i) => (
        <PayWithMpesa key={i} invoiceId={`inv${i}`} onInitiated={() => undefined} label={`Pay ${i}`} />
      ))}
    </>,
  );

describe('the Pay with M-Pesa button follows the school\'s M-Pesa set-up', () => {
  beforeEach(() => {
    resetMpesaAvailability();
    vi.mocked(getMpesaStatus).mockReset();
    signInAt('school-1');
  });

  it('is replaced by a plain explanation when the school has no online M-Pesa', async () => {
    vi.mocked(getMpesaStatus).mockResolvedValue({ enabled: false });
    buttons(1);
    await waitFor(() => expect(screen.getByText(/Online M-Pesa isn.t available for this school yet/)).toBeTruthy());
    expect(screen.queryByText('Pay 0')).toBeNull();
  });

  it('shows the button when online M-Pesa is switched on', async () => {
    vi.mocked(getMpesaStatus).mockResolvedValue({ enabled: true });
    buttons(1);
    await waitFor(() => expect(getMpesaStatus).toHaveBeenCalled());
    expect(screen.getByText('Pay 0')).toBeTruthy();
    expect(screen.queryByText(/isn.t available/)).toBeNull();
  });

  it('keeps the button when the check itself fails: the server will refuse a payment it cannot take, with a clear reason', async () => {
    vi.mocked(getMpesaStatus).mockRejectedValue(new Error('network'));
    buttons(1);
    await waitFor(() => expect(getMpesaStatus).toHaveBeenCalled());
    await act(async () => undefined);
    expect(screen.getByText('Pay 0')).toBeTruthy();
  });

  it('asks once for a whole list of buttons, not once per button', async () => {
    vi.mocked(getMpesaStatus).mockResolvedValue({ enabled: false });
    buttons(6);
    await waitFor(() => expect(screen.getAllByText(/isn.t available/)).toHaveLength(6));
    expect(getMpesaStatus).toHaveBeenCalledTimes(1);
  });

  it('never reuses one school\'s answer for another school signed in on the same page', async () => {
    vi.mocked(getMpesaStatus).mockResolvedValueOnce({ enabled: false }).mockResolvedValueOnce({ enabled: true });
    const first = buttons(1);
    await waitFor(() => expect(screen.getByText(/isn.t available/)).toBeTruthy());
    first.unmount();
    signInAt('school-2');
    buttons(1);
    await waitFor(() => expect(screen.getByText('Pay 0')).toBeTruthy());
    expect(getMpesaStatus).toHaveBeenCalledTimes(2);
  });
});
