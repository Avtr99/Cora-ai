import { describe, it, expect } from 'vitest';

/**
 * Structural smoke test for ChatReadinessBanner exports.
 *
 * NOTE: Full DOM testing requires `@testing-library/react` and
 * `@testing-library/jest-dom`, which are not currently installed.
 * Tests to add once testing-library is available:
 * - Renders nothing when chat is ready
 * - Renders backend-down state with correct copy
 * - Renders LLM-not-configured state with settings action
 * - Renders no-answer-source state with Add documents / Enable web search actions
 */
describe('ChatReadinessBanner structural checks', () => {
  it('ChatReadinessBanner module can be imported', async () => {
    const { ChatReadinessBanner } = await import('./ChatReadinessBanner');
    expect(ChatReadinessBanner).toBeDefined();
    expect(typeof ChatReadinessBanner).toBe('function');
  });

  it('ChatReadinessBanner accepts no props', async () => {
    const mod = await import('./ChatReadinessBanner');
    expect(mod.ChatReadinessBanner.length).toBe(0);
  });
});
