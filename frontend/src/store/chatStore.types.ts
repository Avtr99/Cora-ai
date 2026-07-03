import { RecommendationType } from '@/components/chat/RecommendationCard';
import { CitationResponse, ResponseMetadata, QuizResponse } from '@/services/cora/types';
import { AgentReasoningStep } from '@/types/reasoning';

export type { AgentReasoningStep };

/**
 * Represents a single message in a chat conversation
 */
export interface Message {
  id: string;
  content: string;
  sender: 'user' | 'bot';
  timestamp: Date;
  agentReasoning?: AgentReasoningStep[];
  triggeredRecommendations?: RecommendationType[];
  triggeredRecommendationIds?: string[]; // Specific recommendation IDs that were triggered
  replyToMessageId?: string;
  status?: 'pending' | 'streaming' | 'complete' | 'error' | 'cancelled';
  // citations contains structured metadata from the citation pipeline (e.g. title, url, confidence, snippet).
  // sources is a lightweight list of raw source URLs/identifiers used as a display or fallback reference.
  citations?: CitationResponse;
  sources?: string[];
  metadata?: ResponseMetadata;
  quiz?: QuizResponse;
  suggestedPrompts?: string[];
}

/**
 * Represents a chat conversation with messages and metadata
 */
export interface Chat {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  shownRecommendations: string[]; // Track specific recommendation IDs shown, not just topic types
  backendConversationId?: string; // Canonical conversation ID returned by backend
  historySignature?: string; // HMAC signature for history verification (from backend)
}

/**
 * Core state managed by the chat store
 * Note: Uses plain objects and arrays instead of Map/Set for JSON serialization
 */
export interface ChatState {
  // Core chat data
  chats: Chat[];
  activeChatId: string | null;
  
  // UI state (JSON-serializable)
  typingChatIds: string[];

  // Request management (JSON-serializable, actual AbortControllers managed separately)
  // These store only metadata/IDs; real AbortController instances should be in transient state
  activeRequestControllers: Record<string, boolean>; // chatId -> isActive flag
  pendingBotMessageIds: Record<string, string>; // chatId -> messageId
}

/**
 * Options for getting a bot response
 */
export interface BotResponseOptions {
  targetUserMessageId?: string;
  updateMessageId?: string;
  pendingMessageId?: string;
}

/**
 * Actions available in the chat store
 */
export interface ChatActions {
  // Chat management
  createNewChat: (initialMessage?: string) => Chat | null;
  prepareNewChat: () => void;
  setActiveChat: (chatId: string) => void;
  clearActiveChat: () => void;
  deleteChat: (chatId: string) => void;
  
  // Message handling
  sendMessage: (content: string) => void;
  retryLastUserMessage: () => void;
  retryErrorMessage: (errorMessageId: string) => Promise<void>;
  
  // Internal helper actions (prefixed with _)
  _upsertChatState: (chat: Chat) => void;
  _cancelPendingRequest: (chatId: string, markCancelled?: boolean, removePending?: boolean) => void;
  _detectTopics: (message: string) => RecommendationType[];
  _getBotResponse: (chat: Chat, options?: BotResponseOptions) => Promise<void>;
}

/**
 * Complete chat store type combining state and actions
 */
export type ChatStore = ChatState & ChatActions;
