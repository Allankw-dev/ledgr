import { apiClient } from './client';
import type {
  ChatReportDetail,
  ChatReportSummary,
  DirectContact,
  DirectConversation,
  DirectMessage,
  ReportCategory,
  ReportStatus,
} from '../types';

/** People you can start a private chat with (a teacher's parents / a parent's teachers). */
export async function listDirectContacts(q = ''): Promise<DirectContact[]> {
  const { data } = await apiClient.get<DirectContact[]>('/api/direct/contacts', { params: q ? { q } : undefined });
  return data;
}

export async function listDirectConversations(): Promise<DirectConversation[]> {
  const { data } = await apiClient.get<DirectConversation[]>('/api/direct/conversations');
  return data;
}

/** Start (or reopen) a private chat with someone from your contact list. */
export async function startDirectConversation(userId: string): Promise<DirectConversation> {
  const { data } = await apiClient.post<DirectConversation>('/api/direct/conversations', { user_id: userId });
  return data;
}

export async function listDirectMessages(conversationId: string): Promise<DirectMessage[]> {
  const { data } = await apiClient.get<DirectMessage[]>(`/api/direct/conversations/${conversationId}/messages`);
  return data;
}

export async function sendDirectMessage(conversationId: string, body: string): Promise<DirectMessage> {
  const { data } = await apiClient.post<DirectMessage>(`/api/direct/conversations/${conversationId}/messages`, { body });
  return data;
}

/** Send a photo or document (optionally with a caption). Encrypted before it is stored. */
export async function sendDirectFile(conversationId: string, file: File, caption: string): Promise<DirectMessage> {
  const form = new FormData();
  form.append('file', file);
  form.append('body', caption);
  const { data } = await apiClient.post<DirectMessage>(`/api/direct/conversations/${conversationId}/messages/upload`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

/** Private-chat files are decrypted by the API, so they're fetched with your login (no shareable link). */
export async function fetchDirectAttachment(conversationId: string, messageId: string): Promise<Blob> {
  const { data } = await apiClient.get<Blob>(`/api/direct/conversations/${conversationId}/messages/${messageId}/attachment`, {
    responseType: 'blob',
  });
  return data;
}

/** Delete for everyone (sender only). */
export async function deleteDirectMessage(conversationId: string, messageId: string): Promise<void> {
  await apiClient.delete(`/api/direct/conversations/${conversationId}/messages/${messageId}`);
}

export async function blockUser(userId: string): Promise<void> {
  await apiClient.post('/api/direct/blocks', { user_id: userId });
}

export async function unblockUser(userId: string): Promise<void> {
  await apiClient.delete(`/api/direct/blocks/${userId}`);
}

export async function reportConversation(conversationId: string, category: ReportCategory, details: string): Promise<void> {
  await apiClient.post(`/api/direct/conversations/${conversationId}/report`, { category, details: details || null });
}

// ---- School admin: review reports ----
export async function listChatReports(status?: ReportStatus): Promise<ChatReportSummary[]> {
  const { data } = await apiClient.get<ChatReportSummary[]>('/api/direct/reports', { params: status ? { status } : undefined });
  return data;
}

export async function getChatReport(id: string): Promise<ChatReportDetail> {
  const { data } = await apiClient.get<ChatReportDetail>(`/api/direct/reports/${id}`);
  return data;
}

export async function updateChatReport(id: string, status: ReportStatus, resolutionNote: string): Promise<ChatReportSummary> {
  const { data } = await apiClient.patch<ChatReportSummary>(`/api/direct/reports/${id}`, {
    status,
    resolution_note: resolutionNote || null,
  });
  return data;
}
