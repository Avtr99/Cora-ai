import React, { useMemo, useState, useEffect, Fragment } from 'react';
import {
  HoverCard,
  HoverCardTrigger,
  HoverCardContent,
} from '@/components/ui/hover-card';
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from '@/components/ui/popover';
import { GLOSSARY_MAP, GLOSSARY_REGEX, type GlossaryEntry } from './vcmGlossary';

/**
 * Touch-device detection used to decide whether glossary definitions should
 * open on tap (mobile + tablet) or on hover (desktop only).
 *
 * The previous implementation used `useIsMobile` (width < 768px), which meant
 * tablets — touch devices with no reliable hover — fell back to the
 * HoverCard variant and never showed definitions on tap.
 */
function useIsTouchDevice(): boolean | undefined {
  const [isTouch, setIsTouch] = useState<boolean | undefined>(undefined);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const coarse = window.matchMedia('(hover: none), (pointer: coarse)');
    const update = () => setIsTouch(coarse.matches);

    update();
    coarse.addEventListener('change', update);
    return () => coarse.removeEventListener('change', update);
  }, []);

  return isTouch;
}

/**
 * GlossaryHydrator
 *
 * Scans the text children of a markdown `<p>` node and wraps recognised
 * VCM terms in a Radix HoverCard that shows a contextual definition.
 *
 * Design rules:
 *  – Uses the existing Shadcn HoverCard primitive (no custom popup logic).
 *  – Brand colours from tailwind tokens: `brand-secondary` (#6F4ECB).
 *  – Only the first occurrence of each term per paragraph is hydrated
 *    to avoid visual clutter.
 *  – Matching is case-insensitive, longest-term-first.
 */

// ── Category pill colour map (semantic tokens for theme consistency) ─────────────────────────
const CATEGORY_STYLES: Record<string, string> = {
  Standard:     'bg-brand-100 text-brand-500',
  Registry:     'bg-brand-100 text-brand-500',
  'Core Concept': 'bg-muted text-muted-foreground',
  'Project Type': 'bg-accent text-accent-foreground',
  Market:       'bg-destructive/10 text-destructive',
  Methodology:  'bg-brand-100 text-brand-800',
  'Credit Type': 'bg-destructive/10 text-destructive',
  Unit:         'bg-secondary text-secondary-foreground',
  Governance:   'bg-muted text-muted-foreground',
};

const fallbackCategoryStyle = 'bg-surface-subtle text-text-muted';

// ── Sub-components ────────────────────────────────────────────────────

/** Shared content rendered inside both HoverCard and Popover */
const GlossaryCardContent: React.FC<{ entry: GlossaryEntry }> = ({ entry }) => {
  const pillStyle = entry.category
    ? (CATEGORY_STYLES[entry.category] ?? fallbackCategoryStyle)
    : '';

  return (
    <>
      {/* Category pill */}
      {entry.category && (
        <span
          className={`inline-block mb-2 px-2 py-0.5 rounded-full text-2xs font-semibold uppercase tracking-[0.08em] font-inter ${pillStyle}`}
        >
          {entry.category}
        </span>
      )}

      {/* Term title - show full form (first part before | if present), trimmed */}
      <h4 className="font-poppins text-sm font-semibold tracking-tight leading-snug">
        {entry.term?.split('|')[0]?.trim() ?? entry.term}
      </h4>

      {/* Definition */}
      <p className="mt-1.5 font-inter text-sm leading-[1.55] text-muted-foreground">
        {entry.definition}
      </p>
    </>
  );
};

/** Desktop: hover to show definition */
const DesktopGlossaryTerm: React.FC<{ text: string; entry: GlossaryEntry }> = ({ text, entry }) => (
  <HoverCard openDelay={200} closeDelay={100}>
    <HoverCardTrigger asChild>
      <span
        className="cursor-help underline decoration-dotted decoration-brand-400/50 underline-offset-2 hover:bg-brand-100/60 rounded-sm px-0.5 -mx-0.5 transition-colors duration-150"
        role="term"
        title="Hover for definition"
      >
        {text}
      </span>
    </HoverCardTrigger>
    <HoverCardContent
      align="start"
      sideOffset={6}
      className="z-50 w-[320px] max-w-[calc(100vw-2rem)] rounded-xl border bg-popover text-popover-foreground p-4 shadow-lg"
    >
      <GlossaryCardContent entry={entry} />
    </HoverCardContent>
  </HoverCard>
);

/** Mobile: tap to toggle definition popover */
const MobileGlossaryTerm: React.FC<{ text: string; entry: GlossaryEntry }> = ({ text, entry }) => {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <span
          className="cursor-pointer underline decoration-dotted decoration-brand-400/60 underline-offset-2 active:bg-brand-100/60 rounded-sm px-0.5 -mx-0.5"
          role="term"
          aria-expanded={open}
          title="Tap for definition"
        >
          {text}
        </span>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        sideOffset={6}
        className="z-50 w-[320px] max-w-[calc(100vw-2rem)] rounded-xl border bg-popover text-popover-foreground p-4 shadow-lg"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <GlossaryCardContent entry={entry} />
      </PopoverContent>
    </Popover>
  );
};

// ── Segment splitter ──────────────────────────────────────────────────

interface TextSegment {
  type: 'text' | 'term';
  value: string;
  entry?: GlossaryEntry;
}

/**
 * Splits a plain-text string into alternating text / glossary-term segments.
 * Only hydrates the first occurrence of each term.
 */
function splitByGlossaryTerms(text: string): TextSegment[] {
  const segments: TextSegment[] = [];
  const hydratedTerms = new Set<string>();

  // Reset the regex's lastIndex (it's stateful with the `g` flag)
  GLOSSARY_REGEX.lastIndex = 0;

  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = GLOSSARY_REGEX.exec(text)) !== null) {
    const termLower = match[1].toLowerCase();

    // Skip duplicates within the same paragraph
    if (hydratedTerms.has(termLower)) continue;
    hydratedTerms.add(termLower);

    const entry = GLOSSARY_MAP.get(termLower);
    if (!entry) continue;

    // Leading plain text
    if (match.index > cursor) {
      segments.push({ type: 'text', value: text.slice(cursor, match.index) });
    }

    segments.push({ type: 'term', value: match[0], entry });
    cursor = match.index + match[0].length;
  }

  // Trailing plain text
  if (cursor < text.length) {
    segments.push({ type: 'text', value: text.slice(cursor) });
  }

  return segments;
}

// ── Main component ────────────────────────────────────────────────────

interface GlossaryHydratorProps {
  children: React.ReactNode;
}

/**
 * Drop-in replacement for the default `<p>` renderer in react-markdown.
 * Walks child nodes: plain strings get glossary-scanned, React elements
 * (like `<a>`, `<strong>`, inline citations) pass through untouched.
 */
export const GlossaryHydrator: React.FC<GlossaryHydratorProps> = ({ children }) => {
  const isTouch = useIsTouchDevice();

  const hydrated = useMemo(() => {
    // During SSR/hydration, isTouch is undefined - render placeholder to avoid mismatch.
    // After mount, use the correct component based on device type.
    if (isTouch === undefined) {
      return React.Children.map(children, (child) => {
        if (typeof child !== 'string') return child;
        // Render text without glossary hydration as a placeholder
        return child;
      });
    }

    // Select component inside useMemo to avoid dependency issues.
    // Touch devices (mobile + tablet) use tap-to-open popover; desktop uses hover.
    const TermComponent = isTouch ? MobileGlossaryTerm : DesktopGlossaryTerm;

    return React.Children.map(children, (child) => {
      // Only process raw text strings — leave React elements alone
      if (typeof child !== 'string') return child;

      const segments = splitByGlossaryTerms(child);

      // No glossary matches → return original string
      if (segments.length === 1 && segments[0].type === 'text') {
        return child;
      }

      return segments.map((seg, i) => {
        if (seg.type === 'text') {
          return <Fragment key={i}>{seg.value}</Fragment>;
        }

        return (
          <TermComponent key={i} text={seg.value} entry={seg.entry!} />
        );
      });
    });
  }, [children, isTouch]);

  return (
    <Fragment>
      {hydrated}
    </Fragment>
  );
};
