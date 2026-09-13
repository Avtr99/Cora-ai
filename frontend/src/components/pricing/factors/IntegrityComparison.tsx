import React from 'react';
import { SEMANTIC } from '@/lib/colors';
import {
  INTEGRITY_CHART_ARIA_LABEL,
  INTEGRITY_METHODS,
  INTEGRITY_PRICE_BARS,
  INTEGRITY_SOURCES,
  INTEGRITY_VERSION_NOTE,
  INTEGRITY_VOLUME,
  type MethodologyDecision,
  type MethodologyStatus,
} from '@/data/pricingFactorContent';
import type { ForceId } from '@/data/pricingData';
import BandLabel from '@/components/pricing/shared/BandLabel';
import BarComparison from '@/components/pricing/shared/BarComparison';
import { toBarItems } from '@/components/pricing/shared/barItems';
import ChartPanel from '@/components/pricing/shared/ChartPanel';
import PanelFooter from '@/components/pricing/shared/PanelFooter';
import StatPanel from '@/components/pricing/shared/StatPanel';

/**
 * Status presentation is derived from the typed `MethodologyStatus`, never from
 * a stored display string - so a status can never render without its group or
 * its dot. Colour is carried by the group label as text, not by colour alone.
 */
const METHODOLOGY_STATUS_META: Record<MethodologyStatus, { label: string; dot: string; textClassName: string }> = {
  approved: { label: 'CCP-approved', dot: SEMANTIC.success.icon, textClassName: 'text-semantic-success-text' },
  conditional: { label: 'Conditional', dot: SEMANTIC.warning.icon, textClassName: 'text-semantic-warning-text' },
};

const METHODOLOGY_STATUS_ORDER: MethodologyStatus[] = ['approved', 'conditional'];

const MethodologyRow: React.FC<{ method: MethodologyDecision }> = ({ method }) => (
  <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-x-2.5 py-2.5 pl-3.5 3xl:grid-cols-[7.5rem_minmax(0,1fr)] 4xl:grid-cols-[8.5rem_minmax(0,1fr)]">
    <span className="font-inter text-ui 3xl:text-sm 4xl:text-base font-semibold tabular-nums text-text-primary">
      {method.code}
    </span>
    <span className="font-inter text-ui 3xl:text-sm 4xl:text-base text-text-secondary">{method.name}</span>
    {method.note && (
      <p className="col-start-2 mt-0.5 font-inter text-caption 4xl:text-sm leading-4 text-text-muted">{method.note}</p>
    )}
  </div>
);

const MethodologyGroup: React.FC<{ status: MethodologyStatus; methods: MethodologyDecision[] }> = ({
  status,
  methods,
}) => {
  const meta = METHODOLOGY_STATUS_META[status];
  return (
    <div>
      <p
        className={`flex items-center gap-2 font-inter text-caption 4xl:text-sm font-semibold ${meta.textClassName}`}
      >
        <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: meta.dot }} />
        {meta.label}
      </p>
      <div className="mt-1">
        {methods.map((method) => (
          <MethodologyRow key={method.code} method={method} />
        ))}
      </div>
    </div>
  );
};

const MethodologyList: React.FC = () => (
  <div className="space-y-5 3xl:space-y-6">
    {METHODOLOGY_STATUS_ORDER.map((status) => {
      const methods = INTEGRITY_METHODS.filter((method) => method.status === status);
      return methods.length > 0 ? <MethodologyGroup key={status} status={status} methods={methods} /> : null;
    })}
  </div>
);

const IntegrityComparison: React.FC<{ onForceChange: (force: ForceId) => void }> = ({ onForceChange }) => {
  const items = toBarItems(INTEGRITY_PRICE_BARS);

  return (
    <>
      <ChartPanel
        activeForce="integrity"
        chart={
          <div>
            <BandLabel>Landfill gas</BandLabel>
            <div className="mt-4">
              <BarComparison
                items={items}
                label={INTEGRITY_CHART_ARIA_LABEL}
                valueClassName="text-right font-inter text-body-sm sm:text-body 3xl:text-lg 4xl:text-xl font-semibold text-text-secondary tabular-nums"
              />
            </div>
            <StatPanel stat={INTEGRITY_VOLUME} />
          </div>
        }
        asideLabel="Methodology examples"
        aside={<MethodologyList />}
      />
      <p className="mt-8 max-w-[78ch] font-inter text-caption 3xl:text-xs 4xl:text-sm leading-relaxed text-text-secondary">
        {INTEGRITY_VERSION_NOTE}
      </p>
      <PanelFooter activeForce="integrity" onSelect={onForceChange} sources={INTEGRITY_SOURCES} />
    </>
  );
};

export default IntegrityComparison;
