import React from 'react';
import { Check } from 'lucide-react';
import { KPI } from '@/lib/colors';
import {
  INTEGRITY_BAND_SUB,
  INTEGRITY_CHART_ARIA_LABEL,
  INTEGRITY_METHODS,
  INTEGRITY_PRICE_VIS,
  INTEGRITY_SDG,
  INTEGRITY_SOURCES,
  INTEGRITY_VERSION_NOTE,
  INTEGRITY_VOLUME_ARIA_LABEL,
  INTEGRITY_VOLUME_VIS,
  type MethodologyDecision,
} from '@/data/pricingFactorContent';
import type { ForceId } from '@/data/pricingData';
import Band from '@/components/pricing/shared/Band';
import DataCard from '@/components/pricing/shared/DataCard';
import MiniBars from '@/components/pricing/shared/MiniBars';
import PanelFooter from '@/components/pricing/shared/PanelFooter';
import VerticalBars from '@/components/pricing/shared/VerticalBars';

/**
 * Status presentation is derived from the typed `MethodologyStatus`, never from
 * a stored display string - so a status can never render without its group or
 * its dot. Colour is carried by the group label as text, not by colour alone.
 */
const METHODOLOGY_STATUS_META: Record<
  MethodologyDecision['status'],
  { label: string; textClassName: string }
> = {
  approved: { label: 'CCP-approved', textClassName: 'text-semantic-success-text' },
  conditional: { label: 'Conditional', textClassName: 'text-text-secondary' },
};

const KIND_DOT: Record<MethodologyDecision['kind'], string> = {
  removal: 'bg-kpi-removal',
  reduction: 'bg-kpi-reduction',
};

const KIND_LABEL: Record<MethodologyDecision['kind'], string> = {
  removal: 'Removal',
  reduction: 'Reduction',
};

const StatusIcon: React.FC<{ status: MethodologyDecision['status'] }> = ({ status }) =>
  status === 'approved' ? (
    <span className="grid h-4 w-4 shrink-0 place-items-center rounded-full bg-kpi-removal text-text-inverse">
      <Check aria-hidden="true" strokeWidth={3} className="h-2.5 w-2.5" />
    </span>
  ) : (
    <span
      aria-hidden="true"
      className="h-4 w-4 shrink-0 rounded-full"
      style={{
        boxShadow: `inset 0 0 0 1.5px ${KPI.other}`,
        backgroundImage: `linear-gradient(90deg, ${KPI.other} 50%, transparent 50%)`,
      }}
    />
  );

const MethodologyRow: React.FC<{ method: MethodologyDecision }> = ({ method }) => {
  const meta = METHODOLOGY_STATUS_META[method.status];
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1.5 border-t border-border-ui py-4 first:border-t-0 sm:grid-cols-[7rem_minmax(0,1fr)_9rem]">
      <span className="font-inter text-ui 3xl:text-sm 4xl:text-base font-semibold text-text-primary tabular-nums">
        {method.code}
      </span>
      <span className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 font-inter text-body-sm 3xl:text-body text-text-secondary">
        <span className="font-medium text-text-primary">{method.name}</span>
        <span className="inline-flex items-center gap-2 font-inter text-caption font-medium text-text-muted">
          <span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full ${KIND_DOT[method.kind]}`} />
          {KIND_LABEL[method.kind]}
        </span>
        {method.note ? (
          <span className="basis-full font-inter text-caption leading-snug text-text-muted">{method.note}</span>
        ) : null}
      </span>
      <span
        className={`inline-flex items-center justify-end gap-2 font-inter text-caption 3xl:text-ui font-semibold ${meta.textClassName}`}
      >
        <StatusIcon status={method.status} />
        {meta.label}
      </span>
    </div>
  );
};

const DuoCell: React.FC<{
  title: string;
  subtitle: string;
  children: React.ReactNode;
}> = ({ title, subtitle, children }) => (
  <section className="min-w-0 p-5 3xl:p-6 4xl:p-7 sm:p-7">
    <h4 className="font-poppins text-body-sm 3xl:text-base 4xl:text-lg font-semibold text-text-primary">{title}</h4>
    <p className="mt-1 font-inter text-caption text-text-muted">{subtitle}</p>
    <div className="mt-7">{children}</div>
  </section>
);

const IntegrityComparison: React.FC<{ onForceChange: (force: ForceId) => void }> = ({ onForceChange }) => (
  <>
    <DataCard activeForce="integrity">
      <Band first bare label="Landfill gas after CCP approval" sub={INTEGRITY_BAND_SUB}>
        <div className="grid grid-cols-1 divide-y divide-border-ui md:grid-cols-2 md:divide-x md:divide-y-0">
          <DuoCell title="Average price" subtitle="Before approval = 100">
            <VerticalBars steps={INTEGRITY_PRICE_VIS} label={INTEGRITY_CHART_ARIA_LABEL} />
          </DuoCell>
          <DuoCell title="Traded volume" subtitle="Credits traded per year">
            <VerticalBars steps={INTEGRITY_VOLUME_VIS} label={INTEGRITY_VOLUME_ARIA_LABEL} />
          </DuoCell>
        </div>
      </Band>
      <Band label="Methodology examples">
        <div>
          {INTEGRITY_METHODS.map((method) => (
            <MethodologyRow key={method.code} method={method} />
          ))}
        </div>
        <p className="mt-4 max-w-[78ch] text-pretty font-inter text-caption 3xl:text-ui leading-relaxed text-text-secondary">
          {INTEGRITY_VERSION_NOTE}
        </p>
      </Band>
      <Band label="Co-benefit premium">
        <div className="grid items-center gap-8 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] md:gap-10">
          <div>
            <h4 className="font-poppins text-body-sm 3xl:text-base 4xl:text-lg font-semibold text-text-primary tabular-nums">
              {INTEGRITY_SDG.headline}
            </h4>
            <p className="mt-2 max-w-[42ch] text-pretty font-inter text-caption 3xl:text-ui leading-relaxed text-text-secondary">
              {INTEGRITY_SDG.body}
            </p>
          </div>
          <MiniBars rows={INTEGRITY_SDG.bars} max={100} label={INTEGRITY_SDG.ariaLabel} />
        </div>
      </Band>
    </DataCard>
    <PanelFooter activeForce="integrity" onSelect={onForceChange} sources={INTEGRITY_SOURCES} />
  </>
);

export default IntegrityComparison;
