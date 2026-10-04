import { AxiosError, type AxiosResponse } from 'axios';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthPage } from '../pages/AuthPage';
import { login, verifyTwoFactorLogin } from '../api/auth';

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

function failure(status?: number, detail?: string) {
  const err = new AxiosError('request failed');
  if (status) err.response = { status, data: { detail }, headers: {}, statusText: '', config: {} } as AxiosResponse;
  return err;
}

async function reachCodeScreen() {
  render(
    <MemoryRouter>
      <AuthPage initialMode="login" />
    </MemoryRouter>
  );
  const email = screen.getAllByPlaceholderText(/you@example.com/)[0];
  fireEvent.change(email, { target: { value: 'a@b.com' } });
  fireEvent.change(screen.getAllByLabelText(/Password/)[0], { target: { value: 'pw-pw-pw-pw' } });
  fireEvent.submit(email.closest('form')!);
  await screen.findByText('Two-factor code');
}

async function typeCode() {
  const boxes = screen.getAllByRole('textbox');
  '123456'.split('').forEach((digit, i) => fireEvent.change(boxes[i] ?? boxes[0], { target: { value: digit } }));
  await waitFor(() => expect(verifyTwoFactorLogin).toHaveBeenCalled());
}

beforeEach(() => {
  vi.mocked(verifyTwoFactorLogin).mockReset();
  // (restoreMocks wipes the factory's default, so set the first-step result here)
  vi.mocked(login).mockResolvedValue({ requires_2fa: true, challenge_token: 'chal' } as never);
});

// Every failure used to read "Incorrect code", hiding problems a correct code can't fix.
describe('2FA login error messages', () => {
  it('rate limit', async () => {
    vi.mocked(verifyTwoFactorLogin).mockImplementation(() => Promise.reject(failure(429, 'Too many')));
    await reachCodeScreen();
    await typeCode();
    await screen.findByText(/Too many attempts/);
    expect(document.body.textContent).not.toContain('Incorrect code');
  });

  it('server unreachable', async () => {
    vi.mocked(verifyTwoFactorLogin).mockImplementation(() => Promise.reject(failure()));
    await reachCodeScreen();
    await typeCode();
    await screen.findByText(/reach the server/);
  });

  it('timed-out sign-in sends them back to the password screen', async () => {
    vi.mocked(verifyTwoFactorLogin).mockImplementation(() => Promise.reject(failure(401, 'This login attempt has expired. Please sign in again.')));
    await reachCodeScreen();
    await typeCode();
    await screen.findByText(/sign-in timed out/);
    expect(screen.queryByText('Two-factor code')).toBeNull();
  });

  it('wrong code stays on the code screen with the clock hint', async () => {
    vi.mocked(verifyTwoFactorLogin).mockImplementation(() => Promise.reject(failure(401, 'Incorrect code. Check your authenticator app and try again.')));
    await reachCodeScreen();
    await typeCode();
    await screen.findByText(/Incorrect code\. Wait for the next code/);
    expect(document.body.textContent).toContain('set to automatic');
    expect(screen.getByText('Two-factor code')).toBeTruthy();
  });
});
