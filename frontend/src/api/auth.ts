import { apiClient } from './client';
import type { AuthUser } from '../types';

interface LoginResponse {
  token: string;
  user: AuthUser;
}

interface TwoFactorRequiredResponse {
  requires_2fa: true;
  challenge_token: string;
}

export async function login(email: string, password: string): Promise<LoginResponse | TwoFactorRequiredResponse> {
  const { data } = await apiClient.post<LoginResponse | TwoFactorRequiredResponse>('/api/auth/login', {
    email,
    password,
  });
  return data;
}

export async function verifyTwoFactorLogin(challengeToken: string, code: string): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/api/auth/2fa/verify-login', {
    challenge_token: challengeToken,
    code,
  });
  return data;
}

export async function get2FAStatus(): Promise<{ enabled: boolean }> {
  const { data } = await apiClient.get('/api/auth/2fa/status');
  return data;
}

export async function setup2FA(): Promise<{ secret: string; provisioning_uri: string }> {
  const { data } = await apiClient.post('/api/auth/2fa/setup');
  return data;
}

export async function enable2FA(code: string): Promise<{ enabled: boolean }> {
  const { data } = await apiClient.post('/api/auth/2fa/enable', { code });
  return data;
}

export async function disable2FA(password: string): Promise<{ enabled: boolean }> {
  const { data } = await apiClient.post('/api/auth/2fa/disable', { password });
  return data;
}

export async function registerParent(payload: { full_name: string; email: string; password: string }): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/api/auth/register-parent', payload);
  return data;
}

export async function getSetupStatus(): Promise<{ is_set_up: boolean }> {
  const { data } = await apiClient.get('/api/auth/setup-status');
  return data;
}

interface RegisterSchoolPayload {
  school_name: string;
  country: string;
  currency: string;
  admin_email: string;
  admin_password: string;
  admin_full_name: string;
}

export async function registerSchool(payload: RegisterSchoolPayload): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/api/auth/register-school', payload);
  return data;
}
