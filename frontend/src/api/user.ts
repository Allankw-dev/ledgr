import { apiClient } from './client';

export interface MyProfile {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role: string;
}

export async function getMyProfile(): Promise<MyProfile> {
  const { data } = await apiClient.get<MyProfile>('/api/users/me');
  return data;
}

export async function updateMyProfile(payload: { phone?: string; full_name?: string }): Promise<MyProfile> {
  const { data } = await apiClient.patch<MyProfile>('/api/users/me', payload);
  return data;
}
