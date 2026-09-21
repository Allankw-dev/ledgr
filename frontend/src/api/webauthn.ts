import { apiClient } from './client';
import type { AuthUser } from '../types';

interface WebAuthnLoginResponse {
  token: string;
  refresh_token?: string;
  user: AuthUser;
}

export interface WebAuthnCredentialInfo {
  id: string;
  device_name: string | null;
  created_at: string;
  last_used_at: string | null;
}

export async function getRegisterOptions(): Promise<{ options: Record<string, unknown>; challenge_id: string }> {
  const { data } = await apiClient.post('/api/auth/webauthn/register/options');
  return data;
}

export async function verifyRegistration(
  challengeId: string,
  credential: Record<string, unknown>,
  deviceName: string
): Promise<WebAuthnCredentialInfo> {
  const { data } = await apiClient.post('/api/auth/webauthn/register/verify', {
    challenge_id: challengeId,
    credential,
    device_name: deviceName,
  });
  return data;
}

export async function listWebAuthnCredentials(): Promise<WebAuthnCredentialInfo[]> {
  const { data } = await apiClient.get('/api/auth/webauthn/credentials');
  return data;
}

export async function deleteWebAuthnCredential(id: string): Promise<void> {
  await apiClient.delete(`/api/auth/webauthn/credentials/${id}`);
}

export async function getLoginOptions(): Promise<{ options: Record<string, unknown>; challenge_id: string }> {
  const { data } = await apiClient.post('/api/auth/webauthn/login/options');
  return data;
}

export async function verifyLogin(challengeId: string, credential: Record<string, unknown>): Promise<WebAuthnLoginResponse> {
  const { data } = await apiClient.post<WebAuthnLoginResponse>('/api/auth/webauthn/login/verify', {
    challenge_id: challengeId,
    credential,
  });
  return data;
}
