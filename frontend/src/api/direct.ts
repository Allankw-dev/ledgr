import { apiClient } from './client';
import type { DirectContact, DirectConversation, DirectMessage } from '../types';

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
