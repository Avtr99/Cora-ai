/**
 * Feedback API service
 *
 * Submits chat message feedback (thumbs up/down) to the Cora backend
 * which stores it in the local SQLite database.
 */

export type FeedbackRating = 'positive' | 'negative';

export const FEEDBACK_TAGS = [
  'Inaccurate',
  'Incomplete',
  'Off-topic',
  'Other',
] as const;

export type FeedbackTag = (typeof FEEDBACK_TAGS)[number];

export interface SubmitFeedbackPayload {
  messageId: string;
  chatId?: string;
  userId?: string;
  rating: FeedbackRating;
  tags?: FeedbackTag[];
  comment?: string;
  userQuery?: string;
  botAnswer?: string;
}

/**
 * Submits feedback for a single bot response message.
 * Fire-and-forget on the call-site; throws on network/server error.
 */
export async function submitFeedback(
  payload: SubmitFeedbackPayload,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch('/api/submit-feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    let errorMessage = 'Feedback submission failed';
    try {
      const data = await response.json();
      errorMessage = (data as { error?: string; message?: string }).error || (data as { message?: string }).message || errorMessage;
    } catch {
      const text = await response.text();
      errorMessage = text || errorMessage;
    }
    throw new Error(`${errorMessage} (status ${response.status})`);
  }
}
