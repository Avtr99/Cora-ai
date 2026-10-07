import { apiFetch } from './apiFetch';
import { toCoraResponse, validateQueryResponse } from './cora/streaming';
import { buildBotMessage } from '@/contexts/chat/botMessage';
import { getUnseenRecommendations } from '@/components/chat/recommendationSelection';
import { detectTopics } from '@/store/chatStore.utils';
import type { Chat, Message } from '@/store/chatStore.types';

/**
 * Server-side chat API. Chats live in the instance SQLite database
 * under the owner account; the browser keeps them in memory only.
 *
 * Dev proxy: `/api/chats` is rewritten to `/v1/chats` (vite.config.ts).
 * In production the same prefix is served by the FastAPI `/api` mount.
 */

const CHATS_ENDPOINT = '/api/chats';

export class ChatsApiError extends Error {
  constructor(
    public readonly status: number,
    message?: string
  ) {
    super(message ?? `Chat request failed with status ${status}`);
    this.name = 'ChatsApiError';
  }
}

interface ChatSummaryWire {
  id: string;
  title: string;
  updated_at: string;
}

interface ChatListWire {
  chats: ChatSummaryWire[];
}

interface ChatTurnWire {
  message_id: string;
  answer_id: string;
  user_text: string;
  response: unknown;
  created_at: string;
}

interface ChatDetailWire {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  turns: ChatTurnWire[];
}

/**
 * SQLite `CURRENT_TIMESTAMP` produces "YYYY-MM-DD HH:MM:SS" (UTC, no 'T' or
 * zone suffix), which browsers parse as local time. Normalize to an explicit
 * UTC ISO string first.
 */
function toTimestamp(value: unknown): Date {
  const raw = typeof value === 'string' ? value : '';
  const iso = raw.includes('T') ? raw : `${raw.replace(' ', 'T')}Z`;
  const date = new Date(iso);
  return isNaN(date.getTime()) ? new Date() : date;
}

/** List the owner's chats (summaries only — no messages), newest first. */
export async function listChats(): Promise<Chat[]> {
  const response = await apiFetch(CHATS_ENDPOINT);
  if (!response.ok) {
    throw new ChatsApiError(response.status);
  }
  const data = (await response.json()) as ChatListWire;
  const chats = Array.isArray(data.chats) ? data.chats : [];
  return chats.map((chat) => ({
    id: chat.id,
    title: chat.title,
    messages: [],
    updatedAt: toTimestamp(chat.updated_at),
    shownRecommendations: [],
    messagesLoaded: false,
  }));
}

/**
 * Fetch one chat with all turns and map it to the frontend `Chat` model.
 *
 * Each stored turn becomes a user/bot message pair. The bot message is built
 * by the same `buildBotMessage` used for live answers, and recommendation
 * selection is replayed over the user texts in order so the loaded
 * chat matches what the live session showed.
 */
export async function getChat(chatId: string): Promise<Chat> {
  const response = await apiFetch(`${CHATS_ENDPOINT}/${encodeURIComponent(chatId)}`);
  if (!response.ok) {
    throw new ChatsApiError(response.status);
  }
  const detail = (await response.json()) as ChatDetailWire;

  const messages: Message[] = [];
  const shownRecommendations: string[] = [];

  for (const turn of Array.isArray(detail.turns) ? detail.turns : []) {
    const timestamp = toTimestamp(turn.created_at);
    messages.push({
      id: turn.message_id,
      content: turn.user_text,
      sender: 'user',
      timestamp,
    });

    const detectedTopics = detectTopics(turn.user_text);
    const { topics, recommendationIds } = getUnseenRecommendations(
      detectedTopics,
      shownRecommendations,
      turn.user_text
    );
    shownRecommendations.push(...recommendationIds);

    const coraResponse = toCoraResponse(validateQueryResponse(turn.response));
    messages.push(
      buildBotMessage(coraResponse, turn.message_id, {
        triggeredTopics: topics,
        triggeredRecommendationIds: recommendationIds,
        timestamp,
      })
    );
  }

  return {
    id: detail.id,
    title: detail.title,
    messages,
    updatedAt: toTimestamp(detail.updated_at),
    shownRecommendations,
    messagesLoaded: true,
  };
}

/** Delete a chat on the server. Throws `ChatsApiError` on non-2xx. */
export async function deleteChat(chatId: string): Promise<void> {
  const response = await apiFetch(`${CHATS_ENDPOINT}/${encodeURIComponent(chatId)}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new ChatsApiError(response.status);
  }
}
