import { Chat, Message } from './chatStore.types';
import { RecommendationType } from '@/components/chat/RecommendationCard';
import { sanitizeInput, sanitizeHTML } from '@/lib/security';

// Module-scoped counter for fallback ID generation to prevent collisions
let fallbackCounter = 0;

/**
 * Generate a unique ID with fallback for SSR and older browsers
 * Uses crypto.randomUUID() when available, otherwise falls back to a combination of
 * timestamp + incrementing counter + random segment for guaranteed uniqueness
 */
export const generateId = (): string => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for SSR and older browsers with guaranteed uniqueness
  // Format: timestamp-counter-random (e.g., 1697478234567-1-a3f2k9)
  return `${Date.now()}-${++fallbackCounter}-${Math.random().toString(36).substring(2, 9)}`;
};

/**
 * Generate a title based on the first message
 * Take the first 30 characters and add ellipsis if longer
 */
export const generateChatTitle = (message: string): string => {
  if (message.length <= 30) {
    return message;
  }
  return message.substring(0, 30) + '...';
};

/**
 * Validate and sanitize chat history from localStorage
 * This ensures data integrity and security when loading persisted chats
 */
export const validateAndSanitizeChatHistory = (data: unknown): Chat[] => {
  // Validate structure: must be an array
  if (!Array.isArray(data)) {
    console.warn('Invalid chat history: not an array');
    return [];
  }

  const validatedChats: Chat[] = [];

  for (const chat of data) {
    // Validate required fields
    if (!chat || typeof chat !== 'object') {
      console.warn('Skipping invalid chat object:', chat);
      continue;
    }

    if (typeof chat.id !== 'string' || !chat.id) {
      console.warn('Skipping chat with invalid id:', chat);
      continue;
    }

    if (typeof chat.title !== 'string') {
      console.warn('Skipping chat with invalid title:', chat);
      continue;
    }

    if (!Array.isArray(chat.messages)) {
      console.warn('Skipping chat with invalid messages array:', chat);
      continue;
    }

    // Validate and sanitize messages
    const validatedMessages: Message[] = [];
    for (const msg of chat.messages) {
      if (!msg || typeof msg !== 'object') {
        console.warn('Skipping invalid message:', msg);
        continue;
      }

      if (typeof msg.id !== 'string' || !msg.id) {
        console.warn('Skipping message with invalid id:', msg);
        continue;
      }

      if (typeof msg.content !== 'string') {
        console.warn('Skipping message with invalid content:', msg);
        continue;
      }

      if (msg.sender !== 'user' && msg.sender !== 'bot') {
        console.warn('Skipping message with invalid sender:', msg);
        continue;
      }

      // Sanitize message content (strip HTML tags)
      const sanitizedContent = sanitizeHTML(msg.content);

      // Convert timestamp to Date
      const timestamp = msg.timestamp ? new Date(msg.timestamp) : new Date();
      const timestampInvalid = isNaN(timestamp.getTime());
      if (timestampInvalid) {
        console.warn('Invalid timestamp, using current time:', msg.timestamp);
      }

      validatedMessages.push({
        id: msg.id,
        content: sanitizedContent,
        sender: msg.sender,
        timestamp: timestampInvalid ? new Date() : timestamp,
        agentReasoning: Array.isArray(msg.agentReasoning) ? msg.agentReasoning : undefined,
        triggeredRecommendations: Array.isArray(msg.triggeredRecommendations)
          ? msg.triggeredRecommendations
          : undefined,
        replyToMessageId: typeof msg.replyToMessageId === 'string' ? msg.replyToMessageId : undefined,
        status:
          msg.status === 'pending' ||
          msg.status === 'complete' ||
          msg.status === 'error' ||
          msg.status === 'cancelled'
            ? msg.status
            : undefined,
        citations: msg.citations && typeof msg.citations === 'object' ? msg.citations : undefined,
        sources: Array.isArray(msg.sources) ? msg.sources : undefined,
        metadata: msg.metadata && typeof msg.metadata === 'object' ? msg.metadata : undefined,
        quiz: msg.quiz && typeof msg.quiz === 'object' ? msg.quiz : undefined,
      });
    }

    // Convert createdAt to Date
    const createdAt = chat.createdAt ? new Date(chat.createdAt) : new Date();
    const createdAtInvalid = isNaN(createdAt.getTime());
    if (createdAtInvalid) {
      console.warn('Invalid createdAt, using current time:', chat.createdAt);
    }

    validatedChats.push({
      id: chat.id,
      title: sanitizeInput(chat.title), // Sanitize title
      messages: validatedMessages,
      createdAt: createdAtInvalid ? new Date() : createdAt,
      shownRecommendations: Array.isArray(chat.shownRecommendations) && chat.shownRecommendations.every(id => typeof id === 'string')
        ? chat.shownRecommendations
        : [],
      backendConversationId:
        typeof chat.backendConversationId === 'string' && chat.backendConversationId
          ? sanitizeInput(chat.backendConversationId)
          : undefined,
      historySignature:
        typeof chat.historySignature === 'string' && chat.historySignature
          ? chat.historySignature
          : undefined,
    });
  }

  return validatedChats;
};

/**
 * Detect topics from message content to trigger recommendations
 * Analyzes the message for keywords related to projects, methodologies, and pricing
 */
export const detectTopics = (message: string): RecommendationType[] => {
  const topics: RecommendationType[] = [];
  const lowerMessage = message.toLowerCase();

  // Helper: Check if word exists with word boundaries (avoids "projection" matching "project")
  const hasWord = (word: string): boolean => {
    const regex = new RegExp(`\\b${word}\\b`, 'i');
    return regex.test(message);
  };

  // Helper: Check if phrase exists (for multi-word terms)
  const hasPhrase = (phrase: string): boolean => {
    return lowerMessage.includes(phrase);
  };

  // Helper: Check multiple words (any match)
  const hasAnyWord = (words: string[]): boolean => {
    return words.some(word => hasWord(word));
  };

  // Project-related keywords (includes methodology terms since existing case studies
  // serve as real-world examples of methodologies in practice)
  if (
    hasAnyWord(['project', 'projects']) ||
    hasPhrase('case study') ||
    hasPhrase('co-benefit') ||
    hasPhrase('co-benefits') ||
    hasAnyWord(['renewable', 'reforestation', 'protection', 'conservation']) ||
    hasAnyWord(['methodology', 'methodologies', 'protocol', 'protocols', 'validation', 'verification']) ||
    hasAnyWord(['standard', 'standards']) ||
    hasPhrase('vm0048') ||
    hasPhrase('vm 0048') ||
    hasPhrase('carbon accounting')
  ) {
    topics.push('project');
  }

  // Pricing-related keywords - requires context to avoid false positives
  const hasPricingKeyword = 
    hasAnyWord(['price', 'prices', 'pricing', 'cost', 'costs']) ||
    hasAnyWord(['dollar', 'dollars', 'expensive', 'cheap']) ||
    lowerMessage.includes('$');

  const hasCarbonContext =
    hasAnyWord(['carbon', 'credit', 'credits', 'offset', 'offsets', 'emission', 'emissions']) ||
    hasAnyWord(['vcm', 'market', 'markets']);

  // Explicit pricing phrases that don't need additional context
  const hasExplicitPricingPhrase =
    hasPhrase('price per ton') ||
    hasPhrase('price per tonne') ||
    hasPhrase('cost per ton') ||
    hasPhrase('cost per tonne') ||
    hasPhrase('$/t') ||
    hasPhrase('dollar per ton') ||
    hasPhrase('carbon price') ||
    hasPhrase('carbon pricing') ||
    hasPhrase('credit price') ||
    hasPhrase('offset price');

  if (hasExplicitPricingPhrase || (hasPricingKeyword && hasCarbonContext)) {
    topics.push('pricing');
  }

  return topics;
};
