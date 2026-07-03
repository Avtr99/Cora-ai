/**
 * Lightweight pub/sub channel for streaming token text.
 *
 * Decouples token delivery from the Zustand store so that streaming
 * text updates a single component's local state without triggering
 * global re-renders or virtualizer re-measurements.
 *
 * The channel retains the latest emitted text per message ID so that a
 * subscriber that mounts after the first rAF flush (e.g. a ChatMessage
 * whose useEffect runs after the first token batch) still receives the
 * accumulated text on subscribe.
 */

type Listener = (text: string) => void;

const listenersByMessageId = new Map<string, Set<Listener>>();
const lastTextByMessageId = new Map<string, string>();

/** Subscribe to streaming text updates for a given message ID. */
export function subscribe(messageId: string, listener: Listener): () => void {
  let listeners = listenersByMessageId.get(messageId);
  if (!listeners) {
    listeners = new Set();
    listenersByMessageId.set(messageId, listeners);
  }
  listeners.add(listener);
  // Replay the latest text so a late subscriber doesn't miss tokens
  const last = lastTextByMessageId.get(messageId);
  if (last !== undefined) listener(last);
  return () => {
    listeners?.delete(listener);
    if (listeners && listeners.size === 0) {
      listenersByMessageId.delete(messageId);
      lastTextByMessageId.delete(messageId);
    }
  };
}

/** Emit accumulated streaming text to all subscribers for a message ID. */
export function emit(messageId: string, text: string): void {
  lastTextByMessageId.set(messageId, text);
  listenersByMessageId.get(messageId)?.forEach((fn) => fn(text));
}

/** Clear the channel for a message ID (called on stream end / cleanup). */
export function clear(messageId: string): void {
  listenersByMessageId.delete(messageId);
  lastTextByMessageId.delete(messageId);
}
