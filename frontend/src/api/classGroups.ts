import { apiClient } from './client';
import type {
  ClassGroupSummary,
  ClassGroupMessage,
  GroupMember,
  MessageReceipt,
  AttachmentUrl,
} from '../types';

export async function listClassGroups(): Promise<ClassGroupSummary[]> {
  const { data } = await apiClient.get<ClassGroupSummary[]>('/api/class-groups');
  return data;
}

export async function listClassGroupMessages(classId: string): Promise<ClassGroupMessage[]> {
  const { data } = await apiClient.get<ClassGroupMessage[]>(`/api/class-groups/${classId}/messages`);
  return data;
}

export async function listClassGroupMembers(classId: string): Promise<GroupMember[]> {
  const { data } = await apiClient.get<GroupMember[]>(`/api/class-groups/${classId}/members`);
  return data;
}

export interface SendOptions {
  mentionUserIds?: string[];
  mentionAll?: boolean;
}

export async function sendClassGroupMessage(
  classId: string,
  body: string,
  opts: SendOptions = {}
): Promise<ClassGroupMessage> {
  const { data } = await apiClient.post<ClassGroupMessage>(`/api/class-groups/${classId}/messages`, {
    body,
    mention_user_ids: opts.mentionUserIds ?? [],
    mention_all: opts.mentionAll ?? false,
  });
  return data;
}

/** Send a photo or file, optionally with a caption and @mentions. */
export async function sendClassGroupFile(
  classId: string,
  file: File,
  caption: string,
  opts: SendOptions = {}
): Promise<ClassGroupMessage> {
  const form = new FormData();
  form.append('file', file);
  form.append('body', caption);
  form.append('mention_user_ids', (opts.mentionUserIds ?? []).join(','));
  form.append('mention_all', String(opts.mentionAll ?? false));
  const { data } = await apiClient.post<ClassGroupMessage>(`/api/class-groups/${classId}/messages/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function getAttachmentUrl(classId: string, messageId: string): Promise<AttachmentUrl> {
  const { data } = await apiClient.get<AttachmentUrl>(`/api/class-groups/${classId}/messages/${messageId}/attachment-url`);
  // Local-dev links are relative to the API; Supabase links are already absolute.
  const base = (apiClient.defaults.baseURL || '').replace(/\/$/, '');
  return { ...data, url: data.url.startsWith('http') ? data.url : base + data.url };
}

export async function getMessageReceipts(classId: string, messageId: string): Promise<MessageReceipt[]> {
  const { data } = await apiClient.get<MessageReceipt[]>(`/api/class-groups/${classId}/messages/${messageId}/receipts`);
  return data;
}
