import React from 'react';

export interface CitationGroup {
  numbers: number[];
}

/**
 * Inline citation marker — small, unobtrusive superscript numbers that share
 * the same global numbering as the source list. The minimal style keeps the
 * answer text readable while still giving users a clickable path to sources.
 */
export const InlineCitationPill: React.FC<{
  group: CitationGroup;
  messageId?: string;
}> = ({ group, messageId }) => {
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const elementId = messageId ? `citation-badges-section-${messageId}` : 'citation-badges-section';
    const el = document.getElementById(elementId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const { numbers } = group;
  if (!numbers || numbers.length === 0) return null;

  const title = numbers.length === 1 ? `Source ${numbers[0]}` : `Sources ${numbers.join(', ')}`;
  const label = numbers.join(', ');

  return (
    <button
      type="button"
      onClick={handleClick}
      className="inline-flex items-baseline gap-0.5 ml-0.5 align-super text-[10px] font-medium leading-none text-text-muted hover:text-brand-600 hover:underline focus:outline-none focus:ring-1 focus:ring-brand-500 rounded-sm transition-colors"
      title={title}
      aria-label={`Citation ${label}`}
    >
      {numbers.map((num, idx) => (
        <span key={num}>
          {num}
          {idx < numbers.length - 1 && <span className="mx-0.5">,</span>}
        </span>
      ))}
    </button>
  );
};
