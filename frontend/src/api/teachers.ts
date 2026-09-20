import { apiClient } from './client';
import type { Teacher } from '../types';

export async function listTeachers(): Promise<Teacher[]> {
  const { data } = await apiClient.get<Teacher[]>('/api/teachers');
  return data;
}

export interface NewTeacher {
  fullName: string;
  email?: string;
  phone?: string;
  classIds: string[];
}

export async function createTeacher({ fullName, email, phone, classIds }: NewTeacher): Promise<Teacher> {
  const { data } = await apiClient.post<Teacher>('/api/teachers', {
    full_name: fullName,
    email: email || null,
    phone: phone || null,
    class_ids: classIds,
  });
  return data;
}

export async function resendTeacherInvite(teacherId: string): Promise<Teacher> {
  const { data } = await apiClient.post<Teacher>(`/api/teachers/${teacherId}/resend-invite`);
  return data;
}

export async function updateTeacherClasses(teacherId: string, classIds: string[]): Promise<Teacher> {
  const { data } = await apiClient.patch<Teacher>(`/api/teachers/${teacherId}/classes`, { class_ids: classIds });
  return data;
}
