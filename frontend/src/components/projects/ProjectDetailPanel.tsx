import React from 'react';
import { ExternalLink } from 'lucide-react';
import type { VCMProject } from '@/types/project';
import { getProjectTypeColor, getStatusStyle } from '@/lib/colors';
import { useEnrichedProject } from '@/hooks/useProjectDetail';
import { formatCredits } from '@/lib/formatCredits';
import { IssuanceSparkline } from '@/components/projects/IssuanceSparkline';
import { parseCertifications, type CertificationKind } from '@/lib/certifications';

const CERT_STYLES: Record<CertificationKind, string> = {
  icvcm: 'bg-text-primary text-white border border-text-primary',
  corsia: 'bg-surface-subtle text-text-primary border border-border-ui',
  ccb: 'bg-surface-subtle text-text-primary border border-border-ui',
  other: 'bg-surface-subtle text-text-secondary border border-border-ui',
};

interface ProjectDetailPanelProps {
  project: VCMProject;
  /** Full project list for cohort and developer context. */
  allProjects: VCMProject[];
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

/** Returns the English ordinal suffix for a 0-100 percentile. */
function percentileSuffix(n: number): string {
  if (n >= 11 && n <= 13) return 'th';
  switch (n % 10) {
    case 1: return 'st';
    case 2: return 'nd';
    case 3: return 'rd';
    default: return 'th';
  }
}

/** Converts a raw ARB / WA status into a badge label and style. */
function arbWaBadge(status: string | undefined): { label: string; style: string } | null {
  if (!status) return null;
  const s = status.toLowerCase();
  if (s.includes('not arb') || s.includes('not eligible')) return null;
  if (s.includes('active')) return { label: 'ARB / WA Active', style: 'bg-semantic-success-icon text-white' };
  if (s.includes('completed')) return { label: 'ARB / WA Completed', style: 'bg-semantic-success-button text-white' };
  if (s.includes('proposed')) return { label: 'ARB / WA Proposed', style: 'bg-semantic-warning-icon text-white' };
  if (s.includes('terminated') || s.includes('inactive')) return { label: 'ARB / WA Inactive', style: 'bg-surface-subtle text-text-secondary border border-border-ui' };
  if (s.includes('active project')) return { label: 'ARB / WA Active', style: 'bg-semantic-success-icon text-white' };
  return { label: 'ARB / WA', style: 'bg-surface-subtle text-text-secondary border border-border-ui' };
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

export const ProjectDetailPanel: React.FC<ProjectDetailPanelProps> = ({ project, allProjects, onClose }) => {
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
  const isOverRetired = project.creditsRemaining < 0;
  const certifications = React.useMemo(
    () => parseCertifications(d?.certifications),
    [d?.certifications],
  );

  const MIN_COHORT_SIZE = 10;

  // Precompute lookup indexes once so each detail open only scans its cohort.
  const projectIndexes = React.useMemo(() => {
    const byType = new Map<string, VCMProject[]>();
    const byCountry = new Map<string, VCMProject[]>();
    const byTypeCountry = new Map<string, VCMProject[]>();
    const byDeveloper = new Map<string, VCMProject[]>();
    for (const p of allProjects) {
      if (p.type) {
        const t = byType.get(p.type);
        if (t) t.push(p); else byType.set(p.type, [p]);
        if (p.country) {
          const key = `${p.type}|${p.country}`;
          const tc = byTypeCountry.get(key);
          if (tc) tc.push(p); else byTypeCountry.set(key, [p]);
        }
      }
      if (p.country) {
        const c = byCountry.get(p.country);
        if (c) c.push(p); else byCountry.set(p.country, [p]);
      }
      if (p.developer) {
        const d = byDeveloper.get(p.developer);
        if (d) d.push(p); else byDeveloper.set(p.developer, [p]);
      }
    }
    return { byType, byCountry, byTypeCountry, byDeveloper };
  }, [allProjects]);

  const projectContext = React.useMemo(() => {
    if (project.creditsIssued <= 0) return null;

    const rate = project.creditsRetired / project.creditsIssued;

    const cohortRates = (candidates: VCMProject[]) =>
      candidates
        .filter((p) => p.creditsIssued > 0)
        .map((p) => p.creditsRetired / p.creditsIssued);

    let cohort: 'type+country' | 'type' | 'country' | null = null;
    let values: number[] = [];

    if (project.type && project.country) {
      const arr = cohortRates(projectIndexes.byTypeCountry.get(`${project.type}|${project.country}`) || []);
      if (arr.length >= MIN_COHORT_SIZE) {
        cohort = 'type+country';
        values = arr;
      }
    }

    if (!cohort && project.type) {
      const arr = cohortRates(projectIndexes.byType.get(project.type) || []);
      if (arr.length >= MIN_COHORT_SIZE) {
        cohort = 'type';
        values = arr;
      }
    }

    if (!cohort && project.country) {
      const arr = cohortRates(projectIndexes.byCountry.get(project.country) || []);
      if (arr.length > 0) {
        cohort = 'country';
        values = arr;
      }
    }

    let cohortPercentiles = null;
    if (cohort) {
      values.sort((a, b) => a - b);
      const idx = values.findIndex((v) => v >= rate);
      const rank = idx === -1 ? values.length : idx + 1;
      const percentile = Math.max(1, Math.min(100, Math.round((rank / values.length) * 100)));
      cohortPercentiles = { retiredRate: percentile, cohortSize: values.length, cohort };
    }

    let developerTrackRecord = null;
    if (project.developer) {
      const dev = projectIndexes.byDeveloper.get(project.developer) || [];
      const total = dev.length;
      if (total > 0) {
        const credits = dev.reduce((sum, p) => sum + p.creditsIssued, 0);
        const registered = dev.filter((p) => p.status === 'Registered').length;
        developerTrackRecord = {
          totalProjects: total,
          totalCredits: credits,
          registeredShare: Math.round((registered / total) * 100),
        };
      }
    }

    return { cohortPercentiles, developerTrackRecord };
  }, [projectIndexes, project]);

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
              <span
                className="font-inter text-2xs text-text-secondary"
                title={isOverRetired
                  ? 'Retirements exceed issuances in the source data, so credits remaining is negative.'
                  : undefined}
              >
                Remaining <span className="font-semibold">{formatCredits(project.creditsRemaining)}</span>
                {isOverRetired && <span className="text-text-muted ml-0.5">(over-retired)</span>}
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

        {d?.issuedByYear && (
          <IssuanceSparkline
            issuedByYear={d.issuedByYear}
            hasGap={project.hasIssuanceGap}
          />
        )}

        {d && (
          <>
            {/* Certifications — rendered as badges. parseCertifications drops
                Gold Standard's "Emission Reduction" product label, which is
                not a certification and accounts for most raw values. */}
            {(certifications.length > 0 || d.arbWaStatus) && (
              <div className="mb-4">
                <span className="font-inter text-2xs font-semibold text-text-muted uppercase tracking-[0.5px] block mb-1.5">
                  Compliance & Certifications
                </span>
                <div className="flex flex-wrap gap-2">
                  {(() => {
                    const arb = arbWaBadge(d.arbWaStatus);
                    return arb ? (
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-md font-inter text-xs font-medium ${arb.style}`}>
                        {arb.label}
                      </span>
                    ) : null;
                  })()}
                  {certifications.map((c) => (
                    <span
                      key={c.label}
                      className={`inline-flex items-center px-2.5 py-1 rounded-md font-inter text-xs font-medium ${CERT_STYLES[c.kind]}`}
                    >
                      {c.label}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {projectContext?.cohortPercentiles && (
              <div className="mb-4 p-3 bg-surface-base rounded-xl flex items-start gap-2.5">
                <span className="font-poppins font-semibold text-base text-brand-900 leading-none">
                  {projectContext.cohortPercentiles.retiredRate}
                  <span className="text-[10px] font-medium text-text-muted align-super ml-0.5">
                    {percentileSuffix(projectContext.cohortPercentiles.retiredRate)}
                  </span>
                </span>
                <span className="font-inter text-xs text-text-secondary leading-relaxed pt-0.5">
                  percentile retirement rate among{' '}
                  <span className="font-medium text-text-primary">{projectContext.cohortPercentiles.cohortSize.toLocaleString()}</span>{' '}
                  {projectContext.cohortPercentiles.cohort === 'type+country'
                    ? `${project.type} projects in ${project.country}`
                    : projectContext.cohortPercentiles.cohort === 'type'
                    ? `${project.type} projects`
                    : `projects in ${project.country}`}
                </span>
              </div>
            )}

            {/* Description — promoted to top for context */}
            {d.description && (
              <div className="mb-4 p-3.5 bg-surface-base rounded-xl">
                <span className="font-inter text-2xs font-semibold text-text-muted uppercase tracking-[0.5px] block mb-1.5">
                  About this project
                </span>
                <p className="font-inter text-xs text-text-secondary leading-[1.65] whitespace-pre-line">
                  {d.description}
                </p>
              </div>
            )}

            {projectContext?.developerTrackRecord && (
              <div className="mb-4 p-3.5 bg-surface-base rounded-xl">
                <span className="font-inter text-2xs font-semibold text-text-muted uppercase tracking-[0.5px] block mb-2">
                  Developer track record
                </span>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <span className="font-inter text-2xs text-text-muted block">Projects</span>
                    <span className="font-poppins font-semibold text-sm text-text-primary">
                      {projectContext.developerTrackRecord.totalProjects.toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="font-inter text-2xs text-text-muted block">Credits issued</span>
                    <span className="font-poppins font-semibold text-sm text-text-primary">
                      {formatCredits(projectContext.developerTrackRecord.totalCredits)}
                    </span>
                  </div>
                  <div>
                    <span className="font-inter text-2xs text-text-muted block">Registered</span>
                    <span className="font-poppins font-semibold text-sm text-text-primary">
                      {projectContext.developerTrackRecord.registeredShare}%
                    </span>
                  </div>
                </div>
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
            ]} />

            <FieldGroup title="Timeline" fields={[
              { label: 'Listed', value: d.listed },
              { label: 'Registered', value: d.registered },
              { label: '1st Issuance Year', value: d.firstIssuanceYear },
              { label: 'Last Issuance Year', value: project.lastIssuanceYear },
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
