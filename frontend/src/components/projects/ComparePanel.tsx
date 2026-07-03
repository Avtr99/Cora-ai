import React, { useState } from 'react';
import { X, ExternalLink, ArrowLeftRight, ChevronDown, ChevronUp } from 'lucide-react';
import type { VCMProject } from '@/types/project';
import { useProjectDetailEnricher } from '@/hooks/useProjectDetail';
import { formatCredits } from '@/lib/formatCredits';

interface ComparePanelProps {
  projects: [VCMProject, VCMProject];
  onClose: () => void;
}

function isValidExternalUrl(url: string | undefined): url is string {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

interface MetricRow {
  label: string;
  getValue: (p: VCMProject) => string | number;
  format?: (v: number) => string;
  section: 'metrics' | 'info' | 'details';
}

const METRIC_ROWS: MetricRow[] = [
  { label: 'Credits Issued', getValue: (p) => p.creditsIssued, format: formatCredits, section: 'metrics' },
  { label: 'Credits Retired', getValue: (p) => p.creditsRetired, format: formatCredits, section: 'metrics' },
  { label: 'Credits Remaining', getValue: (p) => p.creditsRemaining, format: formatCredits, section: 'metrics' },
  { label: 'Buffer Pool', getValue: (p) => p._detail?.bufferPool || 0, format: formatCredits, section: 'metrics' },
  { label: 'Registry', getValue: (p) => p.registry, section: 'info' },
  { label: 'Status', getValue: (p) => p.status, section: 'info' },
  { label: 'Type', getValue: (p) => p.type, section: 'info' },
  { label: 'Scope', getValue: (p) => p.scope || '—', section: 'info' },
  { label: 'Country', getValue: (p) => p.country, section: 'info' },
  { label: 'Region', getValue: (p) => p.region || '—', section: 'info' },
  { label: 'Reduction/Removal', getValue: (p) => p.reductionRemoval || '—', section: 'info' },
  { label: 'Methodology', getValue: (p) => p._detail?.methodology || '—', section: 'details' },
  { label: 'Developer', getValue: (p) => p._detail?.developer || p.developer || '—', section: 'details' },
  { label: 'Verifier', getValue: (p) => p._detail?.verifier || '—', section: 'details' },
  { label: 'Listed', getValue: (p) => p._detail?.listed || '—', section: 'details' },
  { label: 'Registered', getValue: (p) => p._detail?.registered || '—', section: 'details' },
];

export const ComparePanel: React.FC<ComparePanelProps> = ({ projects, onClose }) => {
  const { enrichAll, isLoading: detailLoading } = useProjectDetailEnricher();
  const [showDetails, setShowDetails] = useState(false);

  // Show loading state while detail data is being fetched
  if (detailLoading) {
    return (
      <div className="bg-surface-page rounded-2xl border border-border-ui shadow-sm mb-6 overflow-hidden">
        <div className="flex items-center justify-center py-12">
          <div className="flex items-center gap-3">
            <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
            <span className="font-inter text-sm text-text-muted">Loading project details...</span>
          </div>
        </div>
      </div>
    );
  }

  const [a, b] = enrichAll(projects) as [VCMProject, VCMProject];

  const formatValue = (row: MetricRow, val: string | number) => {
    if (row.format && typeof val === 'number') return row.format(val);
    return String(val);
  };

  const isDifferent = (row: MetricRow) => {
    const va = row.getValue(a);
    const vb = row.getValue(b);
    return String(va) !== String(vb);
  };

  const getSectionRows = (section: MetricRow['section']) =>
    METRIC_ROWS.filter((r) => r.section === section);

  const diffCount = METRIC_ROWS.filter(isDifferent).length;

  return (
    <div className="bg-surface-page rounded-2xl border border-border-ui shadow-sm mb-6 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 bg-surface-card border-b border-border-ui">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 bg-surface-subtle rounded-lg">
            <ArrowLeftRight className="w-4 h-4 text-text-muted" />
          </div>
          <div>
            <h2 className="font-poppins font-semibold text-sm text-text-primary">
              Comparing projects
            </h2>
            <span className="font-inter text-xs text-text-muted">
              {diffCount} differences found
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowDetails(!showDetails)}
            aria-label="Toggle details"
            aria-expanded={showDetails}
            className="inline-flex items-center gap-1 font-inter text-xs font-medium px-3 py-1.5 rounded-lg transition-colors border bg-surface-card text-text-secondary border-border-ui hover:bg-surface-base"
          >
            {showDetails ? (
              <><ChevronUp className="w-3.5 h-3.5" /> Less details</>
            ) : (
              <><ChevronDown className="w-3.5 h-3.5" /> More details</>
            )}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 hover:bg-surface-subtle rounded-lg transition-colors"
            aria-label="Close comparison"
          >
            <X className="w-4 h-4 text-text-muted" />
          </button>
        </div>
      </div>

      {/* Comparison Cards - Side by Side */}
      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4 max-w-[1000px] mx-auto">
        {[a, b].map((project) => (
          <div key={project.id} className="bg-surface-card rounded-xl border border-border-ui overflow-hidden">
            {/* Project Header */}
            <div className="px-4 py-3 bg-surface-base border-b border-border-ui">
              <h3 className="font-poppins font-semibold text-sm text-text-primary leading-tight line-clamp-2">
                {project.name}
              </h3>
              <span className="font-inter text-xs text-text-muted mt-0.5 block">
                {project.id} · {project.registry}
              </span>
            </div>

            {/* Key Metrics */}
            <div className="p-4">
              <div className="grid grid-cols-2 gap-3 mb-4">
                {getSectionRows('metrics').map((row) => (
                  <div
                    key={row.label}
                    className={`p-2.5 rounded-lg ${isDifferent(row) ? 'bg-surface-base' : 'bg-surface-subtle'}`}
                  >
                    <span className="font-inter text-2xs text-text-muted block mb-1">
                      {row.label}
                    </span>
                    <span className={`font-poppins font-semibold text-sm ${
                      isDifferent(row) ? 'text-brand-900' : 'text-text-primary'
                    }`}>
                      {formatValue(row, row.getValue(project))}
                    </span>
                  </div>
                ))}
              </div>

              {/* Project Info */}
              <div className="space-y-2 border-t border-surface-subtle pt-3">
                {getSectionRows('info').map((row) => {
                  const isDiff = isDifferent(row);
                  return (
                    <div key={row.label} className="flex justify-between items-baseline">
                      <span className="font-inter text-xs text-text-muted">{row.label}</span>
                      <span className={`font-inter text-xs ${
                        isDiff ? 'text-brand-900 font-medium' : 'text-text-muted'
                      }`}>
                        {formatValue(row, row.getValue(project))}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Additional Details */}
              {showDetails && (
                <div className="space-y-2 border-t border-surface-subtle pt-3 mt-3">
                  {getSectionRows('details').map((row) => {
                    const isDiff = isDifferent(row);
                    return (
                      <div key={row.label} className="flex justify-between items-baseline">
                        <span className="font-inter text-xs text-text-muted">{row.label}</span>
                        <span className={`font-inter text-xs text-right max-w-[60%] ${
                          isDiff ? 'text-brand-900 font-medium' : 'text-text-muted'
                        }`}>
                          {formatValue(row, row.getValue(project))}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Registry Link */}
              {isValidExternalUrl(project._detail?.registryDocs) && (
                <div className="border-t border-surface-subtle pt-3 mt-3">
                  <a
                    href={project._detail?.registryDocs}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 font-inter text-xs text-brand-500 hover:text-brand-900 transition-colors"
                  >
                    View on Registry <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
