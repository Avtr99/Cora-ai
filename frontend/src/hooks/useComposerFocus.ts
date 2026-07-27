import { useEffect, useRef } from 'react';

export interface UseComposerFocusOptions {
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  /** Whether the textarea is currently disabled (e.g. while streaming or rate-limited). */
  disabled: boolean;
  /** Called with a printable character when the user types while focus is elsewhere. */
  onTypeChar: (char: string) => void;
}

/**
 * Focus helpers for the chat composer.
 *
 * - Auto-focuses on desktop (fine pointer + hover) so the cursor is already in
 *   the input on load, without popping open the mobile keyboard.
 * - Refocuses the textarea when `disabled` flips from true to false, restoring
 *   focus after the bot finishes streaming.
 * - "Type anywhere to focus": printable keys typed outside of an input are
 *   forwarded to the composer, matching the behavior of ChatGPT/Slack.
 */
export function useComposerFocus({ textareaRef, disabled, onTypeChar }: UseComposerFocusOptions) {
  const previousDisabledRef = useRef(disabled);
  const onTypeCharRef = useRef(onTypeChar);
  onTypeCharRef.current = onTypeChar;

  // Auto-focus on mount for non-touch devices only.
  useEffect(() => {
    const mql = window.matchMedia('(hover: hover) and (pointer: fine)');
    if (!mql.matches || disabled) return;

    const ta = textareaRef.current;
    if (!ta) return;

    const t = setTimeout(() => ta.focus(), 0);
    return () => clearTimeout(t);
  }, [disabled, textareaRef]);

  // Refocus when the textarea becomes enabled (e.g. streaming finished).
  useEffect(() => {
    if (previousDisabledRef.current && !disabled) {
      textareaRef.current?.focus();
    }
    previousDisabledRef.current = disabled;
  }, [disabled, textareaRef]);

  // Type anywhere to focus.
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.defaultPrevented) return;
      if (disabled) return;
      if (e.repeat || e.isComposing || e.ctrlKey || e.altKey || e.metaKey) return;

      const target = e.target;
      if (!(target instanceof HTMLElement)) return;

      const tag = target.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (target.isContentEditable || target.closest('[contenteditable="true"]')) return;
      if (target.closest('button, a[href], [role="button"], [role="menuitem"]')) return;

      const key = e.key;
      if (key.length !== 1) return;

      e.preventDefault();
      onTypeCharRef.current(key);
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [disabled]);
}
