import React from 'react';

export interface CitationGroup {
  sourceLabel: string;
  numbers: number[];
}

export const InlineCitationPill: React.FC<{
  group: CitationGroup;
  messageId?: string;
}> = ({ group, messageId }) => {
  const isKB = group.sourceLabel === 'Knowledge Base';

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const elementId = messageId ? `citation-badges-section-${messageId}` : 'citation-badges-section';
    const el = document.getElementById(elementId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const basePillClass = `
    inline-flex items-center justify-center
    h-5 min-w-5 px-1.5 py-0
    rounded text-[11px] font-semibold leading-none
    border transition-colors cursor-pointer
    focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-1
  `;

  const kbPillClass = `${basePillClass} bg-brand-100 text-brand-700 border-brand-300 hover:bg-brand-200 hover:border-brand-400`;
  const webPillClass = `${basePillClass} bg-surface-subtle text-text-secondary border-border-ui hover:bg-surface-subtle hover:border-border-ui`;

  if (group.numbers.length === 0) {
    return (
      <button
        type="button"
        onClick={handleClick}
        className={isKB ? kbPillClass : webPillClass}
        title={`Source: ${group.sourceLabel}`}
        aria-label={`Citation from ${group.sourceLabel}`}
      >
        {isKB ? 'KB' : 'Web'}
      </button>
    );
  }

  return (
    <span className="inline-flex items-center gap-[2px] mx-1 align-baseline">
      {group.numbers.map((num, idx) => (
        <button
          key={`${group.sourceLabel}-${num}-${idx}`}
          type="button"
          onClick={handleClick}
          className={isKB ? kbPillClass : webPillClass}
          title={`${group.sourceLabel}, source ${num}`}
          aria-label={`Citation ${num} from ${group.sourceLabel}`}
        >
          {num}
        </button>
      ))}
    </span>
  );
};
