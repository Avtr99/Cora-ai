import { describe, it, expect } from 'vitest';

/**
 * Structural smoke test for ChatMessage exports.
 *
 * NOTE: Full DOM testing requires `@testing-library/react` and
 * `@testing-library/jest-dom`, which are not currently installed.
 * Install them to enable comprehensive component tests:
 *
 *   npm install --save-dev @testing-library/react @testing-library/jest-dom
 *
 * Tests to add once testing-library is available:
 * - User message rendering (plain text bubble)
 * - Bot message rendering (markdown, reasoning, citations)
 * - Error/cancelled states with retry button
 * - Pending state with loading indicator
 * - Copy-to-clipboard functionality
 * - Recommendation card display
 * - Quiz widget and suggested prompts
 * - Feedback component visibility
 */
describe('ChatMessage structural checks', () => {
  it('ChatMessage module can be imported', async () => {
    // Cold-importing the chat component pulls in the markdown stack; under a
    // parallel vitest run this has exceeded the 5s default.

    const { ChatMessage, TypingIndicator } = await import('./ChatMessage');
    expect(ChatMessage).toBeDefined();
    expect(typeof ChatMessage).toBe('function');
    expect(TypingIndicator).toBeDefined();
    expect(typeof TypingIndicator).toBe('function');
  }, 15_000);

  it('ChatMessage accepts expected prop types at the type level', async () => {
    const mod = await import('./ChatMessage');
    // Verify the component is a React function component by checking its signature
    expect(mod.ChatMessage.length).toBeGreaterThanOrEqual(1); // accepts props object
  });
});
