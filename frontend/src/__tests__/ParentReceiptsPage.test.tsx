import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { ParentReceiptsPage } from '../pages/ParentReceiptsPage';
import { makeChild } from '../test/fixtures';

vi.mock('../components/ParentShell', () => ({ ParentShell: ({ children }: { children: ReactNode }) => <div>{children}</div> }));
vi.mock('../components/DownloadReceiptLink', () => ({
  DownloadReceiptLink: ({ paymentId }: { paymentId: string }) => <a href={`#${paymentId}`}>Receipt {paymentId}</a>,
}));

const children = vi.hoisted(() => ({ value: [] as unknown[] }));
vi.mock('../hooks/useMyChildren', () => ({
  useMyChildren: () => ({ children: children.value, loading: false, error: null }),
}));

describe('ParentReceiptsPage', () => {
  it('shows a split M-Pesa payment as one receipt and reveals the breakdown on request', () => {
    children.value = [
      makeChild('a', 'Alex Karimi', [
        { due_date: '2026-10-31T00:00:00Z', payments: [{ id: 'p1', amount: 56010, reference_code: 'RCP1' }] },
        { due_date: '2027-03-29T00:00:00Z', payments: [{ id: 'p2', amount: 3990, reference_code: 'RCP1' }] },
      ]),
    ];
    render(<ParentReceiptsPage />);

    // the parent paid once: one total, not two lines — but the breakdown is hidden until asked for
    expect(screen.getAllByText(/Ksh\s60,000/).length).toBeGreaterThan(0);
    expect(screen.queryByText('Receipt p1')).toBeNull();

    fireEvent.click(screen.getAllByRole('button', { name: /Split across 2 invoices/ })[0]);
    expect(screen.getAllByText('Receipt p1').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Receipt p2').length).toBeGreaterThan(0);
    expect(document.body.textContent).toContain('Invoice due 31 Oct 2026');
  });

  it('keeps an ordinary single payment as a plain row with its receipt link', () => {
    children.value = [makeChild('a', 'Alex Karimi', [{ payments: [{ id: 'solo', amount: 1000, reference_code: 'R9' }] }])];
    render(<ParentReceiptsPage />);
    expect(screen.queryByRole('button', { name: /Split across/ })).toBeNull();
    expect(screen.getAllByText('Receipt solo').length).toBeGreaterThan(0);
  });
});
