import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PayWithMpesa } from '../components/PayWithMpesa';
import { requestMpesaPayment } from '../api/parent';

vi.mock('../api/parent', () => ({
  requestMpesaPayment: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(requestMpesaPayment).mockResolvedValue({ checkout_request_id: 'x', message: 'ok' });
});

function open(label: string) {
  fireEvent.click(screen.getByText(label));
}

describe('PayWithMpesa — several children', () => {
  it('names the child in the title, the panel, the button and the confirmation', async () => {
    const onInitiated = vi.fn();
    render(
      <PayWithMpesa
        studentId="s1"
        childName="Alex Karimi"
        detail="Whole outstanding balance"
        balance={66020}
        defaultPhone="0712345678"
        onInitiated={onInitiated}
        label="Pay for Alex with M-Pesa"
      />
    );
    open('Pay for Alex with M-Pesa');
    expect(screen.getByText('Pay for Alex')).toBeTruthy();
    expect(screen.getByText('Paying school fees for')).toBeTruthy();
    expect(screen.getByText('Alex Karimi')).toBeTruthy();
    expect(screen.getByText('Whole outstanding balance')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Amount to pay in shillings'), { target: { value: '30000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Pay KES 30,000 for Alex' }));

    // whole-balance button sends the STUDENT, not an invoice
    await waitFor(() =>
      expect(requestMpesaPayment).toHaveBeenCalledWith({ invoiceId: undefined, studentId: 's1' }, '0712345678', 30000)
    );
    expect(onInitiated).toHaveBeenCalledWith('Alex Karimi');
    await waitFor(() =>
      expect(document.body.textContent).toContain("to pay Alex Karimi's fees has been sent to 0712345678")
    );
  });
});

describe('PayWithMpesa — one child / one invoice', () => {
  it('shows no child panel and the plain title', () => {
    render(<PayWithMpesa invoiceId="i1" balance={500} onInitiated={() => {}} />);
    open('Pay now');
    expect(screen.queryByText('Paying school fees for')).toBeNull();
    expect(screen.getByText('Pay with M-Pesa')).toBeTruthy();
    expect(screen.getByText('Still owed on this invoice')).toBeTruthy();
  });

  it('refuses an amount larger than what is owed and sends nothing', () => {
    render(<PayWithMpesa invoiceId="i1" balance={500} defaultPhone="0712345678" onInitiated={() => {}} />);
    open('Pay now');
    fireEvent.change(screen.getByLabelText('Amount to pay in shillings'), { target: { value: '501' } });
    expect(document.body.textContent).toContain('more than the');
    expect((screen.getByRole('button', { name: /send payment request/i }) as HTMLButtonElement).disabled).toBe(true);
    expect(requestMpesaPayment).not.toHaveBeenCalled();
  });
});
