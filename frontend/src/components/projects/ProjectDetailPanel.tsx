import React from 'react';
import { ExternalLink } from 'lucide-react';
import type { VCMProject } from '@/types/project';
import { getProjectTypeColor, getStatusStyle } from '@/lib/colors';
import { useEnrichedProject } from '@/hooks/useProjectDetail';
import { formatCredits } from '@/lib/formatCredits';

interface ProjectDetailPanelProps {
  project: VCMProject;
  onClose?: () => void;
}

interface FieldProps {
  label: string;
  value: string | number | undefined;
}

const Field: React.FC<FieldProps> = ({ label, value }) => {
  const displayValue = value === undefined || value === '' ? null : String(value);
  if (!displayValue) return null;
  return (
    <div className="flex justify-between py-2.5 gap-4 border-b border-surface-subtle last:border-0">
      <span className="font-inter text-[11px] text-text-muted flex-shrink-0">{label}</span>
      <span className="font-inter text-[12px] text-text-primary text-right max-w-[60%] break-words font-medium">
        {displayValue}
      </span>
    </div>
  );
};

/** Flat section header — always visible, no collapse */
const SectionHeader: React.FC<{ title: string }> = ({ title }) => (
  <div className="pt-5 pb-2 border-b border-border-ui">
    <span className="font-inter text-2xs font-semibold text-text-muted uppercase tracking-[0.6px]">
      {title}
    </span>
  </div>
);

interface FieldItem {
  label: string;
  value: string | number | undefined;
}

interface FieldGroupProps {
  title: string;
  fields: FieldItem[];
}

/** Renders a group of fields, returns null if all fields are empty */
const FieldGroup: React.FC<FieldGroupProps> = ({ title, fields }) => {
  // Check if any field has a non-empty value (excluding 0 as valid)
  const hasContent = fields.some(f => f.value !== undefined && f.value !== '');
  if (!hasContent) return null;

  return (
    <>
      <SectionHeader title={title} />
      <div>
        {fields.map((f) => (
          <Field key={f.label} label={f.label} value={f.value} />
        ))}
      </div>
    </>
  );
};

export const ProjectDetailPanel: React.FC<ProjectDetailPanelProps> = ({ project, onClose }) => {
  const enriched = useEnrichedProject(project);
  const d = enriched?._detail;
  const typeColor = getProjectTypeColor(project.type);
  const statusStyle = getStatusStyle(project.status);

  const totalCredits = project.creditsIssued || 1;
  const rawRetiredPct = (project.creditsRetired / totalCredits) * 100;
  const retiredPct = project.creditsRetired > 0
    ? Math.max(1, Math.min(100, Math.round(rawRetiredPct)))
    : 0;
  const remainingPct = 100 - retiredPct;
  const retiredLabel = rawRetiredPct > 0 && rawRetiredPct < 0.5 ? '<1%' : `${retiredPct}%`;

  return (
    <div className="h-full flex flex-col bg-surface-card">
      {/* Header — clean, no accent bar */}
      <div className="flex-shrink-0 border-b border-border-ui px-5 pt-5 pb-4">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="font-inter text-2xs font-medium px-2 py-0.5 rounded bg-surface-subtle text-text-secondary">
              {project.id}
            </span>
            <span
              className="inline-flex items-center gap-1 font-inter text-2xs font-semibold px-2 py-0.5 rounded uppercase"
              style={{ backgroundColor: statusStyle.bg, color: statusStyle.text }}
            >
              <span className="w-1 h-1 rounded-full" style={{ backgroundColor: statusStyle.dot }} />
              {project.status}
            </span>
            <span className="font-inter text-2xs text-text-muted">{project.registry}</span>
          </div>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 hover:bg-surface-subtle rounded-lg transition-colors lg:hidden flex-shrink-0"
              aria-label="Close project details"
            >
              <svg className="w-4 h-4 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
        <h2 className="font-poppins font-semibold text-base text-text-primary leading-[1.35]">
          {project.name}
        </h2>
        <div className="flex items-center gap-1.5 mt-1.5">
          {project.type && (
            <span
              className="inline-block px-1.5 py-0.5 rounded text-2xs font-medium font-inter"
              style={{ backgroundColor: typeColor.bg, color: typeColor.text }}
            >
              {project.type}
            </span>
          )}
          {project.country && (
            <span className="font-inter text-xs text-text-muted">{project.country}</span>
          )}
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto scrollbar-hide px-5 py-4">
        {/* Horizontal stacked credit bar — uses top-level fields, always visible */}
        <div className="mb-5">
          <div className="flex items-baseline justify-between mb-2">
            <span className="font-poppins font-semibold text-lg text-text-primary">
              {formatCredits(project.creditsIssued)}
            </span>
            <span className="font-inter text-xs text-text-muted">credits issued</span>
          </div>

          <div className="h-2 rounded-full bg-surface-subtle overflow-hidden flex mb-2">
            <div
              className="h-full transition-all duration-300 bg-chart-retired"
              style={{ width: `${retiredPct}%` }}
              title={`Retired: ${retiredPct}%`}
            />
            <div
              className="h-full transition-all duration-300 bg-border-ui"
              style={{ width: `${remainingPct}%` }}
              title={`Remaining: ${remainingPct}%`}
            />
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-sm bg-chart-retired" />
              <span className="font-inter text-2xs text-text-secondary">
                Retired <span className="font-semibold">{formatCredits(project.creditsRetired)}</span>
                <span className="text-text-muted ml-0.5">({retiredLabel})</span>
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-sm bg-border-ui" />
              <span className="font-inter text-2xs text-text-secondary">
                Remaining <span className="font-semibold">{formatCredits(project.creditsRemaining)}</span>
              </span>
            </div>
          </div>

          {d?.annualReductions ? (
            <div className="flex justify-between mt-2 pt-2 border-t border-surface-subtle">
              <span className="font-inter text-xs text-text-muted">Est. Annual Reductions</span>
              <span className="font-inter text-xs text-text-primary font-medium">{formatCredits(d.annualReductions)}</span>
            </div>
          ) : null}
        </div>

        {/* Detail sections — wait for _detail to load */}
        {!d && (
          <div className="flex items-center justify-center py-8">
            <span className="font-inter text-xs text-text-muted animate-pulse">Loading details…</span>
          </div>
        )}

        {d && (
          <>
            {/* Description — promoted to top for context */}
            {d.description && (
              <div className="mb-4 p-3.5 bg-surface-base rounded-xl">
                <span className="font-inter text-2xs font-semibold text-text-muted uppercase tracking-[0.5px] block mb-1.5">
                  About this project
                </span>
                <p className="font-inter text-xs text-text-secondary leading-[1.65]">
                  {d.description}
                </p>
              </div>
            )}

            {/* Links */}
            {(d.registryDocs || d.projectWebsite) && (
              <div className="flex gap-2 mb-4">
                {d.registryDocs && (
                  <a
                    href={d.registryDocs}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 text-center px-3 py-2 rounded-lg border border-border-ui font-inter text-xs font-medium text-text-primary hover:bg-surface-subtle transition-colors inline-flex items-center justify-center gap-1.5"
                  >
                    <ExternalLink className="w-3 h-3" /> Registry
                  </a>
                )}
                {d.projectWebsite && (
                  <a
                    href={d.projectWebsite}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 text-center px-3 py-2 rounded-lg border border-border-ui font-inter text-xs font-medium text-text-primary hover:bg-surface-subtle transition-colors inline-flex items-center justify-center gap-1.5"
                  >
                    <ExternalLink className="w-3 h-3" /> Website
                  </a>
                )}
              </div>
            )}

            {/* All sections open by default — no collapsing */}
            <FieldGroup title="Overview" fields={[
              { label: 'Type', value: project.type },
              { label: 'Scope', value: project.scope },
              { label: 'Reduction / Removal', value: project.reductionRemoval },
              { label: 'Registry Project Type', value: d.registryType },
            ]} />

            <FieldGroup title="Location" fields={[
              { label: 'Region', value: project.region },
              { label: 'Country', value: project.country },
              { label: 'State', value: d.state },
              { label: 'Site Location', value: d.siteLocation },
            ]} />

            <FieldGroup title="Stakeholders" fields={[
              { label: 'Developer', value: d.developer },
              { label: 'Owner', value: d.owner },
              { label: 'Operator', value: d.operator },
              { label: 'Designee', value: d.designee },
              { label: 'Verifier', value: d.verifier },
            ]} />

            <FieldGroup title="Methodology" fields={[
              { label: 'Protocol', value: d.methodology },
              { label: 'Version', value: d.methodologyVersion },
              { label: 'Certifications', value: d.certifications },
            ]} />

            <FieldGroup title="Timeline" fields={[
              { label: 'Listed', value: d.listed },
              { label: 'Registered', value: d.registered },
              { label: '1st Issuance Year', value: d.firstIssuanceYear },
            ]} />

            <FieldGroup title="Regulatory" fields={[
              { label: 'ARB / WA Project', value: d.arbWaProject },
              { label: 'ARB / WA Status', value: d.arbWaStatus },
              { label: 'ARB / WA ID', value: d.arbWaId },
              { label: 'PoA / Aggregate ID', value: d.poaId },
              { label: 'PoA / VPA Status', value: d.poaStatus },
            ]} />

            {/* Notes */}
            {(d.registryNotes || d.berkeleyNotes) && (
              <>
                <SectionHeader title="Notes" />
                <div className="py-2 space-y-2">
                  {d.registryNotes && (
                    <div className="p-3 bg-surface-base rounded-lg">
                      <div className="font-inter text-2xs font-semibold text-text-muted mb-1">From Registry</div>
                      <p className="font-inter text-xs text-text-secondary leading-relaxed">{d.registryNotes}</p>
                    </div>
                  )}
                  {d.berkeleyNotes && (
                    <div className="p-3 bg-surface-base rounded-lg">
                      <div className="font-inter text-2xs font-semibold text-text-muted mb-1">Berkeley Carbon Trading Project</div>
                      <p className="font-inter text-xs text-text-secondary leading-relaxed">{d.berkeleyNotes}</p>
                    </div>
                  )}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
};
