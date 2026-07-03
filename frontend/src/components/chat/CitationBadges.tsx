import React from 'react';
import { Database, Globe, ExternalLink } from 'lucide-react';
import { sanitizeUrl } from '@/lib/security';

export interface CitationSource {
  label: string;
  url?: string;
  type: 'knowledge_base' | 'web';
}

interface CitationBadgesProps {
  sources: CitationSource[];
  messageId: string;
}

/**
 * Get a friendly source name from a URL or label
 * - Backend now automatically URL-decodes and strips file extensions
 * - We only extract domain for URLs and clean up paths
 */
function getSourceDisplayName(label: string): string {
  // Backend now handles: URL decoding, extension stripping (.jsonl, .md, .pdf)
  // We only do minimal path cleaning for display
  let cleaned = label.replace(/^data[\\/]/, '').trim();

  if (cleaned.includes('%') || cleaned.includes('+')) {
    try {
      let decoded = cleaned.replace(/\+/g, ' ');
      let guard = 0;
      while (decoded.includes('%') && guard < 5) {
        const next = decodeURIComponent(decoded);
        if (next === decoded) break;
        decoded = next;
        guard++;
      }
      cleaned = decoded;
    } catch {
      // Keep original cleaned label if decoding fails
    }
  }

  // Preserve methodology IDs (VM0047, VCS1764, ACM0001, etc.) as uppercase
  cleaned = cleaned.replace(/(VM|VCS|ACM|AMS|CCQI)\d+/gi, (match) => match.toUpperCase());

  // If it looks like a URL, extract domain
  if (cleaned.includes('.')) {
    try {
      const url = cleaned.startsWith('http') ? new URL(cleaned) : new URL(`https://${cleaned}`);
      const domain = url.hostname.replace(/^www\./, '');
      // Remove common TLDs for cleaner display
      return domain.replace(/\.(com|org|net|edu|gov|io|co\.\w{2})$/, '');
    } catch {
      // Not a valid URL, return cleaned label
    }
  }

  return cleaned;
}

/**
 * Get a simplified domain for icon display
 */
function getSourceIconKey(label: string): string {
  const lower = label.toLowerCase();

  // TODO: Keys such as github/stackoverflow/verra/goldstandard/berkeley/boell/opendata
  // currently fall back to the default Globe icon in SourceIcon. Add explicit icon cases
  // when vetted brand-safe vectors are available for the design system.
  // Web sources
  if (lower.includes('wikipedia')) return 'wikipedia';
  if (lower.includes('reddit')) return 'reddit';
  if (lower.includes('medium')) return 'medium';
  if (lower.includes('github')) return 'github';
  if (lower.includes('stackoverflow')) return 'stackoverflow';
  if (lower.includes('verra')) return 'verra';
  if (lower.includes('goldstandard') || lower.includes('gs.')) return 'goldstandard';
  if (lower.includes('berkeley')) return 'berkeley';
  if (lower.includes('boell')) return 'boell';
  if (lower.includes('opendata')) return 'opendata';

  // KB sources
  if (lower.includes('vm') || lower.includes('ams') || lower.includes('acm')) return 'methodology';
  if (lower.includes('ccqi')) return 'ccqi';

  return 'generic';
}

/**
 * Source icon component with fallback to Lucide icons
 */
const SourceIcon: React.FC<{ type: 'knowledge_base' | 'web'; label: string }> = ({ type, label }) => {
  const iconKey = getSourceIconKey(label);

  // KB sources use database icon
  if (type === 'knowledge_base') {
    return <Database className="h-3.5 w-3.5 text-brand-700" />;
  }

  // Web sources - could be extended with custom SVGs for popular sites
  switch (iconKey) {
    case 'wikipedia':
      return (
        <svg className="h-3.5 w-3.5 text-text-muted" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.8" />
          <path
            d="M7 8L8.8 16L12 10L15.2 16L17 8"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case 'reddit':
      return (
        <svg className="h-3.5 w-3.5 text-semantic-warning-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="10" fill="currentColor" />
          <circle cx="8" cy="10" r="1.5" fill="white" />
          <circle cx="16" cy="10" r="1.5" fill="white" />
          <path d="M8 14c0 2.5 1.8 4 4 4s4-1.5 4-4" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" />
        </svg>
      );
    case 'medium':
      return (
        <svg className="h-3.5 w-3.5 text-text-primary" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="10" fill="currentColor" />
          <circle cx="12" cy="12" r="2" fill="white" />
        </svg>
      );
    default:
      return <Globe className="h-3.5 w-3.5 text-text-muted" />;
  }
};

/**
 * CitationBadges - Displays sources as numbered pill badges
 * Similar to the design in the reference image with numbered pills
 * containing icons and source names
 */
export const CitationBadges: React.FC<CitationBadgesProps> = ({ sources, messageId }) => {
  if (!sources || sources.length === 0) return null;

  // Group sources by type
  const kbSources = sources.filter(s => s.type === 'knowledge_base');
  const webSources = sources.filter(s => s.type === 'web');

  return (
    <div id={`citation-badges-section-${messageId}`} className="mt-3 space-y-2 w-full">
      {/* Knowledge Base Sources */}
      {kbSources.length > 0 && (
        <div className="flex flex-wrap md:flex-nowrap items-center gap-2">
          <span className="font-inter font-normal text-xs text-text-secondary mr-1 whitespace-nowrap shrink-0">Knowledge Base:</span>
          {kbSources.map((source, index) => (
            <CitationBadge
              key={`kb-${index}`}
              number={index + 1}
              source={source}
            />
          ))}
        </div>
      )}

      {/* Web Sources */}
      {webSources.length > 0 && (
        <div className="flex flex-wrap md:flex-nowrap items-center gap-2">
          <span className="font-inter font-normal text-xs text-text-secondary mr-1 whitespace-nowrap shrink-0">Web:</span>
          {webSources.map((source, index) => (
            <CitationBadge
              key={`web-${index}`}
              number={index + 1}
              source={source}
            />
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * Individual citation badge pill
 */
const CitationBadge: React.FC<{ number: number; source: CitationSource }> = ({ number, source }) => {
  const displayName = getSourceDisplayName(source.label);
  const safeUrl = source.url ? sanitizeUrl(source.url) : null;

  const badgeContent = (
    <>
      {/* Number circle */}
      <span className="flex items-center justify-center w-4 h-4 rounded-full bg-surface-subtle text-2xs font-normal text-text-secondary">
        {number}
      </span>
      {/* Icon */}
      <span className="flex-shrink-0">
        <SourceIcon type={source.type} label={source.label} />
      </span>
      {/* Source name */}
      <span className="font-inter font-normal text-xs leading-[1.4] text-text-primary truncate whitespace-nowrap min-w-0 max-w-[40vw] sm:max-w-[240px] md:max-w-[120px] lg:max-w-[150px]">
        {displayName}
      </span>
    </>
  );

  const baseBadgeClass = "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border-ui bg-surface-card hover:bg-surface-subtle hover:border-border-ui transition-colors max-w-full min-w-0";
  const interactiveBadgeClass = `${baseBadgeClass} cursor-pointer`;

  if (safeUrl) {
    return (
      <a
        href={safeUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={interactiveBadgeClass}
        aria-label={`Open source ${source.label} (opens in a new tab)`}
        title={`Open ${source.label}`}
      >
        {badgeContent}
        <ExternalLink className="h-2.5 w-2.5 text-text-muted ml-0.5" />
        <span className="sr-only">(opens in a new tab)</span>
      </a>
    );
  }

  return (
    <span className={baseBadgeClass} title={source.label}>
      {badgeContent}
    </span>
  );
};
