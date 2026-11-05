import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useRef } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthPage } from '../pages/AuthPage';
import { registerParent } from '../api/auth';
import { resubscribeWithToken, unsubscribeWithToken } from '../api/privacy';
import { CookieNotice } from '../components/CookieNotice';
import { Modal } from '../components/ui/Modal';
import { SiteFooter } from '../components/SiteFooter';
import { PrivacyPage } from '../pages/legal/PrivacyPage';
import { RefundPage } from '../pages/legal/RefundPage';
import { TermsPage } from '../pages/legal/TermsPage';
import { CookiePage } from '../pages/legal/CookiePage';
import { UnsubscribePage } from '../pages/UnsubscribePage';

vi.mock('../api/auth', () => ({
  login: vi.fn(),
  verifyTwoFactorLogin: vi.fn(),
  googleAuth: vi.fn(),
  registerParent: vi.fn(),
}));
vi.mock('../api/webauthn', () => ({
  isPlatformAuthenticatorAvailable: () => Promise.resolve(false),
  getLoginOptions: vi.fn(),
  performAuthentication: vi.fn(),
  verifyLogin: vi.fn(),
}));
vi.mock('../api/privacy', () => ({
  unsubscribeWithToken: vi.fn(),
  resubscribeWithToken: vi.fn(),
  getPrivacySettings: vi.fn(),
  setEmailOptOut: vi.fn(),
  deleteMyAccount: vi.fn(),
}));

beforeEach(() => {
  localStorage.clear();
  vi.mocked(unsubscribeWithToken).mockResolvedValue(undefined);
  vi.mocked(resubscribeWithToken).mockResolvedValue(undefined);
});

describe('legal pages', () => {
  it.each([
    ['Privacy Policy', PrivacyPage],
    ['Terms of Service', TermsPage],
    ['Refund Policy', RefundPage],
    ['Cookie Policy', CookiePage],
  ])('%s is readable without signing in and links to the other policies', (title, Page) => {
    render(<MemoryRouter><Page /></MemoryRouter>);
    expect(screen.getByRole('heading', { level: 1, name: title })).toBeTruthy();
    const legalNav = screen.getByRole('navigation', { name: 'Legal' });
    expect(legalNav.querySelectorAll('a')).toHaveLength(4);
  });

  it('shows a visible "operator to add" notice instead of inventing business details', () => {
    render(<MemoryRouter><PrivacyPage /></MemoryRouter>);
    expect(screen.getAllByText(/operator to add/).length).toBeGreaterThan(0);
  });

  it('the footer links to all four policies', () => {
    render(<MemoryRouter><SiteFooter /></MemoryRouter>);
    for (const name of ['Privacy Policy', 'Terms of Service', 'Refund Policy', 'Cookie Policy']) {
      expect(screen.getByRole('link', { name })).toBeTruthy();
    }
  });
});

describe('storage notice', () => {
  it('shows until dismissed, then stays dismissed', () => {
    const { unmount } = render(<MemoryRouter><CookieNotice /></MemoryRouter>);
    expect(screen.getByRole('region', { name: /cookie and storage notice/i })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /ok, got it/i }));
    expect(screen.queryByRole('region', { name: /cookie and storage notice/i })).toBeNull();
    unmount();
    render(<MemoryRouter><CookieNotice /></MemoryRouter>);
    expect(screen.queryByRole('region', { name: /cookie and storage notice/i })).toBeNull();
  });
});

describe('unsubscribe page', () => {
  it('asks first, and only unsubscribes after the click', async () => {
    render(<MemoryRouter initialEntries={['/unsubscribe?token=abc123abc123']}><UnsubscribePage /></MemoryRouter>);
    expect(unsubscribeWithToken).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /yes, unsubscribe me/i }));
    await screen.findByText(/you are unsubscribed/i);
    expect(unsubscribeWithToken).toHaveBeenCalledWith('abc123abc123');
    fireEvent.click(screen.getByRole('button', { name: /turn emails back on/i }));
    await screen.findByText(/emails are back on/i);
    expect(resubscribeWithToken).toHaveBeenCalledWith('abc123abc123');
  });

  it('says so when the link has no token', () => {
    render(<MemoryRouter initialEntries={['/unsubscribe']}><UnsubscribePage /></MemoryRouter>);
    expect(screen.getByText(/invalid or has expired/i)).toBeTruthy();
  });
});

describe('sign-up consent', () => {
  function fillSignup() {
    fireEvent.change(screen.getByPlaceholderText('e.g. Jane Wambui'), { target: { value: 'Jane Wambui' } });
    fireEvent.change(screen.getByPlaceholderText('e.g. +254712345678'), { target: { value: '0712345678' } });
    const form = screen.getByPlaceholderText('e.g. Jane Wambui').closest('form')!;
    fireEvent.change(form.querySelector('input[autocomplete="new-password"]')!, { target: { value: 'Str0ng-pass-word' } });
    fireEvent.change(screen.getByPlaceholderText('e.g. GA-2026-014'), { target: { value: 'GA-1' } });
  }

  it('both boxes start unticked and sign-up is refused until they are ticked', async () => {
    render(<MemoryRouter><AuthPage initialMode="signup" /></MemoryRouter>);
    const terms = screen.getByRole('checkbox', { name: /accept the terms of service/i }) as HTMLInputElement;
    const guardian = screen.getByRole('checkbox', { name: /parent or legal guardian/i }) as HTMLInputElement;
    expect(terms.checked).toBe(false);
    expect(guardian.checked).toBe(false);

    fillSignup();
    fireEvent.submit(screen.getByPlaceholderText('e.g. Jane Wambui').closest('form')!);
    await screen.findByText(/accept the Terms of Service and Privacy Policy to continue/i);
    expect(registerParent).not.toHaveBeenCalled();

    fireEvent.click(terms);
    fireEvent.submit(screen.getByPlaceholderText('e.g. Jane Wambui').closest('form')!);
    await screen.findByText(/18 or older and the child/i);
    expect(registerParent).not.toHaveBeenCalled();
  });

  it('sends both confirmations to the server once ticked', async () => {
    vi.mocked(registerParent).mockResolvedValue({ token: 't', refresh_token: 'r', user: { id: 'u', role: 'PARENT' } } as never);
    render(<MemoryRouter><AuthPage initialMode="signup" /></MemoryRouter>);
    fillSignup();
    fireEvent.click(screen.getByRole('checkbox', { name: /accept the terms of service/i }));
    fireEvent.click(screen.getByRole('checkbox', { name: /parent or legal guardian/i }));
    fireEvent.submit(screen.getByPlaceholderText('e.g. Jane Wambui').closest('form')!);
    await waitFor(() => expect(registerParent).toHaveBeenCalled());
    expect(vi.mocked(registerParent).mock.calls[0][0]).toMatchObject({ accept_terms: true, confirm_guardian: true });
  });
});

describe('dialog keyboard behaviour', () => {
  function Harness() {
    const ref = useRef<HTMLButtonElement>(null);
    return (
      <div>
        <button ref={ref}>opener</button>
        <Modal title="Test dialog" onClose={() => {}}>
          <input aria-label="first" />
          <button>last</button>
        </Modal>
      </div>
    );
  }

  it('moves focus into the dialog and keeps Tab inside it', () => {
    render(<Harness />);
    const first = screen.getByLabelText('first');
    expect(document.activeElement).toBe(first);
    const last = screen.getByRole('button', { name: 'last' });
    last.focus();
    fireEvent.keyDown(last, { key: 'Tab' });
    expect(screen.getByRole('dialog').contains(document.activeElement)).toBe(true);
  });
});
