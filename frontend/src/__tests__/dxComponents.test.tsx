import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import { GaugeCard } from '../components/dx/GaugeCard';
import { BalancesTable } from '../components/dx/BalancesTable';
import { AdminRail } from '../components/dx/RightRail';
import { NotificationsProvider } from '../components/NotificationsContext';

vi.mock('../api/auditLogs', () => ({ listAuditLogs: vi.fn() }));
vi.mock('../api/teachers', () => ({ listTeachers: vi.fn() }));
import { listAuditLogs } from '../api/auditLogs';
import { listTeachers } from '../api/teachers';

const wrap = (ui: React.ReactNode) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('GaugeCard', () => {
  it('clamps what it shows to 0-100%', () => {
    const { rerender } = render(<GaugeCard label="Goal" percent={140} />);
    expect(screen.getByText('100%')).toBeTruthy();
    rerender(<GaugeCard label="Goal" percent={-5} />);
    expect(screen.getByText('0%')).toBeTruthy();
    rerender(<GaugeCard label="Goal" percent={Number.NaN} />);
    expect(screen.getByText('0%')).toBeTruthy();
  });
});

describe('BalancesTable', () => {
  it('lists students with their balances, or says there are none', () => {
    const row = { invoice_id: 'i1', student_id: 's1', student_name: 'Danny Otieno', class_name: 'Grade 5', balance: '84200', risk_score: 91, risk_level: 'high' as const };
    const { unmount } = wrap(<BalancesTable rows={[row]} />);
    expect(screen.getByText('Danny Otieno')).toBeTruthy();
    expect(screen.getByText('Grade 5')).toBeTruthy();
    expect(document.body.textContent).toMatch(/84,200/);
    unmount();
    wrap(<BalancesTable rows={[]} />);
    expect(screen.getByText('No high-risk unpaid invoices right now.')).toBeTruthy();
  });
});

describe('AdminRail', () => {
  const notif = { unreadMessages: 2, unreadClassGroups: 0, mentions: [] } as unknown as ComponentProps<typeof NotificationsProvider>['value'];

  beforeEach(() => {
    vi.mocked(listAuditLogs).mockReset();
    vi.mocked(listTeachers).mockReset();
  });

  function renderRail() {
    return wrap(
      <NotificationsProvider value={notif}>
        <AdminRail overdueCount={4} flaggedCount={0} />
      </NotificationsProvider>
    );
  }

  it('shows notifications, recent activity and teacher contacts', async () => {
    vi.mocked(listAuditLogs).mockResolvedValue({
      items: [{ id: 'a1', actor_name: 'Josh Kamau', action: 'PAYMENT_RECORDED', created_at: new Date().toISOString() }],
      meta: { page: 1, page_size: 5, total: 1, total_pages: 1 },
    } as never);
    vi.mocked(listTeachers).mockResolvedValue([
      { id: 't1', full_name: 'Daniel Craig', email: 'd@x.com', phone: '+254700000001', is_active: true, class_names: ['Grade 5'] },
      { id: 't2', full_name: 'Retired Person', email: 'r@x.com', phone: null, is_active: false, class_names: [] },
    ] as never);
    renderRail();

    expect(screen.getByText('2 new messages from parents')).toBeTruthy();
    expect(screen.getByText('4 invoices overdue')).toBeTruthy();
    await waitFor(() => expect(screen.getByText('Payment Recorded')).toBeTruthy());
    await waitFor(() => expect(screen.getByText('Daniel Craig')).toBeTruthy());
    // Inactive teachers are not contacts; the first reachable one is highlighted with quick actions.
    expect(screen.queryByText('Retired Person')).toBeNull();
    expect(screen.getByLabelText('Email Daniel Craig').getAttribute('href')).toBe('mailto:d@x.com');
    expect(screen.getByLabelText('Call Daniel Craig').getAttribute('href')).toBe('tel:+254700000001');
  });

  it('says so, instead of staying blank, when the extra panels fail to load', async () => {
    vi.mocked(listAuditLogs).mockRejectedValue(new Error('403'));
    vi.mocked(listTeachers).mockRejectedValue(new Error('500'));
    renderRail();
    await waitFor(() => expect(screen.getByText("Couldn't load recent activity.")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("Couldn't load contacts.")).toBeTruthy());
  });
});
