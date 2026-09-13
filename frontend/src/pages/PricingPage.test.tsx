import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PricingPage from './PricingPage';
import { FORCE_ORDER, FORCES } from '@/data/pricingData';

vi.mock('@/components/icons/IconWrapper', () => ({ IconWrapper: () => null }));
vi.mock('../components/ui/ScrollToTop', () => ({ ScrollToTop: () => null }));
vi.mock('framer-motion', async (importOriginal) => ({
  ...await importOriginal<typeof import('framer-motion')>(),
  useReducedMotion: () => true,
}));

let container: HTMLDivElement;
let root: Root;

beforeEach(async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
  await act(async () => {
    root.render(<MemoryRouter><PricingPage /></MemoryRouter>);
  });
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
});

describe('Pricing page', () => {
  it('connects every factor tab to a keyboard-focusable panel', () => {
    const tabs = container.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    expect(tabs).toHaveLength(5);
    for (const tab of tabs) {
      const panel = document.getElementById(tab.getAttribute('aria-controls')!);
      expect(panel?.getAttribute('role')).toBe('tabpanel');
    }
    expect(container.querySelector<HTMLElement>('[role="tabpanel"]')?.tabIndex).toBe(0);
  });

  it.each(FORCE_ORDER)('shows the %s evidence and source links when selected', async (id) => {
    const tab = container.querySelector<HTMLButtonElement>(`#pricing-tab-${id}`)!;
    await act(async () => tab.click());
    const panel = container.querySelector<HTMLElement>('[role="tabpanel"]')!;
    expect(tab.getAttribute('aria-selected')).toBe('true');
    expect(panel.getAttribute('aria-labelledby')).toBe(tab.id);
    expect(panel.querySelector('h2')?.textContent).toBe(FORCES[id].label);
    expect(panel.querySelectorAll('a[target="_blank"]').length).toBeGreaterThan(0);
  });

  it('supports arrow keys, Home, and End with roving focus', async () => {
    const first = container.querySelector<HTMLButtonElement>('#pricing-tab-type')!;
    first.focus();
    for (const [key, expected] of [['ArrowLeft', 'vintage'], ['ArrowRight', 'type'], ['End', 'vintage'], ['Home', 'type']]) {
      await act(async () => {
        document.activeElement!.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
      });
      expect(document.activeElement?.id).toBe(`pricing-tab-${expected}`);
      expect(document.activeElement?.getAttribute('aria-selected')).toBe('true');
      expect(container.querySelectorAll('[role="tab"][tabindex="0"]')).toHaveLength(1);
    }
  });

  it('moves focus to the selected tab when following a related factor', async () => {
    const related = Array.from(container.querySelectorAll('button')).find((button) => button.textContent === 'See claim eligibility')!;
    related.focus();
    await act(async () => related.click());
    expect(document.activeElement?.id).toBe('pricing-tab-claims');
    expect(document.activeElement?.getAttribute('aria-selected')).toBe('true');
  });

  it('shows the active factor headline stat in the hero', async () => {
    const heroStat = container.querySelector('[data-testid="pricing-hero-stat"]')!;
    expect(heroStat.textContent).toContain('381%');
    const vintageTab = container.querySelector<HTMLButtonElement>('#pricing-tab-vintage')!;
    await act(async () => vintageTab.click());
    expect(container.querySelector('[data-testid="pricing-hero-stat"]')?.textContent).toContain('217%');
    const complianceTab = container.querySelector<HTMLButtonElement>('#pricing-tab-compliance')!;
    await act(async () => complianceTab.click());
    expect(container.querySelector('[data-testid="pricing-hero-stat"]')?.textContent).toContain('Jan 2028');
  });

  it('preserves the reported prices and proportional bar lengths', () => {
    const chart = container.querySelector('[role="img"]')!;
    expect(chart.textContent).toContain('$4.05');
    expect(chart.textContent).toContain('$19.50');
    expect(chart.textContent).toContain('$160+');
    const widths = Array.from(chart.querySelectorAll<HTMLElement>('[style]')).map((bar) => parseFloat(bar.style.width));
    expect(widths).toHaveLength(3);
    // Bars stay proportional to price but keep a minimum visible width
    // so the smallest value never collapses to an invisible dot.
    expect(widths[0]).toBeGreaterThanOrEqual(6);
    expect(widths[1]).toBeGreaterThan(widths[0]);
    expect(widths[2]).toBe(100);
  });
});
