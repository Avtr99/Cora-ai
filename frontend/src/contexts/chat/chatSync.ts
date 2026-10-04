import { useChatStore } from '@/store/chatStore.simple';
import { ChatsApiError, getChat, listChats } from '@/services/chatsApi';

/**
 * Server chat synchronization (Phase 7). Chats persist on the server; these
 * helpers fill the in-memory store from the chats API.
 */

/**
 * Load the owner's chat list once. Called by ChatProvider on mount; a
 * second call while a load is in-flight or finished is a no-op.
 */
export async function loadChatList(): Promise<void> {
  const store = useChatStore.getState();
  if (store.listStatus !== 'idle') return;

  store.setListStatus('loading');
  try {
    const remoteChats = await listChats();
    const state = useChatStore.getState();
    state.mergeServerChats(remoteChats);
    state.setListStatus('ready');
  } catch (error) {
    console.error('[ChatContext] Failed to load chats from server:', error);
    // Local chats are kept: a failed list fetch must not drop in-flight turns.
    useChatStore.getState().setListStatus('error');
  }
}

/**
 * Fetch the messages of a server-listed chat (messagesLoaded === false) and
 * fill them into the store.
 *
 * - 404: the chat was deleted on another device — remove it locally (the
 *   store's deleteChat also clears activeChatId when it was active).
 * - Other errors: logged, the chat stays with an empty message area and can
 *   be retried by reopening it.
 */
export async function loadChatMessages(chatId: string): Promise<void> {
  const store = useChatStore.getState();
  if (store.loadingChatIds.includes(chatId)) return;

  const chat = store.chats.find((c) => c.id === chatId);
  if (!chat || chat.messagesLoaded) return;

  store.markChatLoading(chatId);
  try {
    const detail = await getChat(chatId);
    useChatStore.getState().mergeChatHistory(chatId, detail);
  } catch (error) {
    if (error instanceof ChatsApiError && error.status === 404) {
      useChatStore.getState().deleteChat(chatId);
    } else {
      console.error('[ChatContext] Failed to load chat messages:', error);
    }
  } finally {
    useChatStore.getState().unmarkChatLoading(chatId);
  }
}
