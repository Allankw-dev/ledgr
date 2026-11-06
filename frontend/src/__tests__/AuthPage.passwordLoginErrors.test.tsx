import { AxiosError, type AxiosResponse } from 'axios';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { AuthPage } from '../pages/AuthPage';
import { login } from '../api/auth';

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

function failure(status?: number) {
  const err = new AxiosError('request failed');
  if (status) err.response = { status, data: {}, headers: {}, statusText: '', config: {} } as AxiosResponse;
  return err;
}

async function submitPassword() {
  render(
    <MemoryRouter>
      <AuthPage initialMode="login" />
    </MemoryRouter>
  );
  const email = screen.getAllByPlaceholderText(/you@example.com/)[0];
  fireEvent.change(email, { target: { value: 'a@b.com' } });
  fireEvent.change(screen.getAllByLabelText(/Password/)[0], { target: { value: 'pw-pw-pw-pw' } });
  fireEvent.submit(email.closest('form')!);
}

// A database error once made every login say "Incorrect email/phone or password", which sent the owner looking for a
// typo instead of a broken deployment.
describe('password sign-in error messages', () => {

  it('says incorrect only when the server rejected the credentials', async () => {
    vi.mocked(login).mockImplementation(() => Promise.reject(failure(401)));
    await submitPassword();
    await screen.findByText(/Incorrect email\/phone or password/);
  });

  it('a server error is not blamed on the password', async () => {
    vi.mocked(login).mockImplementation(() => Promise.reject(failure(500)));
    await submitPassword();
    await screen.findByText(/problem on our side/);
    expect(document.body.textContent).not.toContain('Incorrect email/phone or password');
  });

  it('a lockout says to wait', async () => {
    vi.mocked(login).mockImplementation(() => Promise.reject(failure(429)));
    await submitPassword();
    await screen.findByText(/Too many attempts/);
    expect(document.body.textContent).not.toContain('Incorrect email/phone or password');
  });

  it('a lost connection says so', async () => {
    vi.mocked(login).mockImplementation(() => Promise.reject(failure()));
    await submitPassword();
    await screen.findByText(/Can't reach Ledgr/);
  });
});
