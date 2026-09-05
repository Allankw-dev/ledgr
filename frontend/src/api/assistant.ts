import { apiClient } from './client';

export interface AssistantMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AssistantAction {
  tool: string;
  result_summary: string;
}

interface AssistantChatResponse {
  reply: string;
  actions_taken: AssistantAction[];
}

export async function sendAssistantMessage(
  message: string,
  history: AssistantMessage[]
): Promise<AssistantChatResponse> {
  const { data } = await apiClient.post<AssistantChatResponse>('/api/assistant/chat', {
    message,
    history,
  });
  return data;
}
