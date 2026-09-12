import { apiClient } from './client';
import type { Teacher } from '../types';

export async function listTeachers(): Promise<Teacher[]> {
  const { data } = await apiClient.get<Teacher[]>('/api/teachers');
  return data;
}

export async function createTeacher(fullName: string, email: string, classIds: string[]): Promise<Teacher> {
  const { data } = await apiClient.post<Teacher>('/api/teachers', {
    full_name: fullName,
    email,
    class_ids: classIds,
  });
  return data;
}

export async function updateTeacherClasses(teacherId: string, classIds: string[]): Promise<Teacher> {
  const { data } = await apiClient.patch<Teacher>(`/api/teachers/${teacherId}/classes`, { class_ids: classIds });
  return data;
}
