import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, vi } from 'vitest';

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

  it('ChatMarkdownContent renders markdown horizontal rules as visually hidden separators with spacing', async () => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    const { ChatMarkdownContent } = await import('./ChatMarkdownContent');
    const container = document.createElement('div');
    document.body.append(container);
    const root = createRoot(container);

    try {
      await act(async () => {
        root.render(
          <ChatMarkdownContent
            content={'First section\n\n---\n\nSecond section'}
            messageId="m1"
            mounted={true}
            copyText={vi.fn()}
          />
        );
      });

      const hr = container.querySelector('hr');
      expect(hr).not.toBeNull();
      expect(hr?.classList.contains('sr-only')).toBe(true);
      expect(hr?.getAttribute('aria-hidden')).toBeNull();
      expect(hr?.closest('[aria-hidden="true"]')).toBeNull();
      expect(hr?.parentElement?.className).toContain('my-4');
      expect(hr?.parentElement?.className).toContain('md:my-5');
      expect(hr?.parentElement?.className).toContain('3xl:my-6');
      expect(hr?.parentElement?.className).toContain('4xl:my-7');
    } finally {
      await act(async () => root.unmount());
      container.remove();
      vi.unstubAllGlobals();
    }
  });

  it('ChatMarkdownContent applies section-to-paragraph spacing hierarchy across headings and paragraphs', async () => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    const { ChatMarkdownContent } = await import('./ChatMarkdownContent');
    const container = document.createElement('div');
    document.body.append(container);
    const root = createRoot(container);

    try {
      await act(async () => {
        root.render(
          <ChatMarkdownContent
            content={'### What they represent\nFirst paragraph\n\n---\n\n### How they are used\nSecond paragraph'}
            messageId="m2"
            mounted={true}
            copyText={vi.fn()}
          />
        );
      });

      const headings = container.querySelectorAll('h3');
      expect(headings).toHaveLength(2);
      expect(headings[0]?.className).toContain('first:mt-0');
      expect(headings[0]?.className).toContain('mb-2');
      expect(headings[1]?.className).toContain('mt-5');
      expect(headings[1]?.className).toContain('md:mt-6');

      const paragraphs = container.querySelectorAll('p');
      expect(paragraphs).toHaveLength(2);
      expect(paragraphs[0]?.className).toContain('mb-3');
      expect(paragraphs[0]?.className).toContain('last:mb-0');
    } finally {
      await act(async () => root.unmount());
      container.remove();
      vi.unstubAllGlobals();
    }
  });

  it('AgentReasoningSection keeps summary hit target at >=24px and separates from answer across breakpoints', async () => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    const { AgentReasoningSection } = await import('./AgentReasoningSection');
    const container = document.createElement('div');
    document.body.append(container);
    const root = createRoot(container);

    try {
      await act(async () => {
        root.render(
          <AgentReasoningSection
            steps={[{ agentName: 'Understand the question', messages: ['Refined wording'], status: 'complete', kind: 'understand' }]}
            status="complete"
          />
        );
      });

      const details = container.querySelector('details');
      const summary = container.querySelector('summary');
      expect(details?.className).toContain('mb-4');
      expect(details?.className).toContain('md:mb-5');
      expect(details?.className).toContain('3xl:mb-6');
      expect(details?.className).toContain('4xl:mb-8');
      expect(summary?.className).toContain('min-h-6');
      expect(summary?.className).toContain('py-0.5');
    } finally {
      await act(async () => root.unmount());
      container.remove();
      vi.unstubAllGlobals();
    }
  });
});
