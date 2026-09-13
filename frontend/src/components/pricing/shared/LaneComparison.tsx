import React from 'react';
import { SEMANTIC } from '@/lib/colors';
import type { MethodologyRef, StatusTone } from '@/data/pricingFactorContent';

const StatusLine: React.FC<{ tone: StatusTone; children: React.ReactNode }> = ({ tone, children }) => (
  <p
    className={`flex items-center gap-2 font-inter text-ui 3xl:text-sm font-semibold ${
      tone === 'success' ? 'text-semantic-success-text' : 'text-semantic-warning-text'
    }`}
  >
    <span
      aria-hidden="true"
      className="h-[7px] w-[7px] shrink-0 rounded-full"
      style={{ backgroundColor: tone === 'success' ? SEMANTIC.success.icon : SEMANTIC.warning.icon }}
    />
    {children}
  </p>
);

export const FlowLine: React.FC<{ from: string; to: string }> = ({ from, to }) => (
  <p className="font-inter text-body-sm 3xl:text-body 4xl:text-lg text-text-secondary">
    {from}
    <span aria-hidden="true" className="px-1.5 text-text-muted">
      →
    </span>
    <span className="font-semibold text-text-primary">{to}</span>
  </p>
);

export const DemandText: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <p className="max-w-[44ch] text-pretty font-inter text-body-sm 3xl:text-body 4xl:text-lg leading-relaxed text-text-secondary">
    {children}
  </p>
);

/** Bulleted buyer-pool list. Sizes match DemandText so lanes read evenly. */
export const BulletList: React.FC<{ items: string[] }> = ({ items }) => (
  <ul className="space-y-1.5">
    {items.map((item) => (
      <li
        key={item}
        className="flex gap-2 font-inter text-body-sm 3xl:text-body 4xl:text-lg leading-relaxed text-text-secondary"
      >
        <span aria-hidden="true" className="mt-[0.55em] h-1 w-1 shrink-0 rounded-full bg-text-disabled" />
        <span className="min-w-0">{item}</span>
      </li>
    ))}
  </ul>
);

const DetailLabel: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <p className="font-inter text-overline font-semibold uppercase tracking-wider text-text-muted">{children}</p>
);

export const MethodologyChips: React.FC<{ items: MethodologyRef[] }> = ({ items }) => (
  <ul className="flex flex-wrap gap-2">
    {items.map((item) => (
      <li
        key={item.code}
        className="inline-flex items-center gap-1.5 rounded-full bg-surface-subtle px-2.5 3xl:px-3 4xl:px-3.5 py-1 3xl:py-1.5 4xl:py-2 font-inter text-xs 3xl:text-sm 4xl:text-base text-text-secondary"
      >
        <span className="font-semibold tabular-nums text-text-primary">{item.code}</span>
        <span>{item.name}</span>
      </li>
    ))}
  </ul>
);

export interface LaneSection {
  label: string;
  content: React.ReactNode;
}

export interface Lane {
  title: string;
  tone: StatusTone;
  status: string;
  sections: LaneSection[];
}

const LaneCard: React.FC<Lane> = ({ title, tone, status, sections }) => (
  <section className="min-w-0 p-6 sm:p-7 3xl:p-8">
    <h4 className="text-balance font-poppins text-base sm:text-lg 3xl:text-xl font-semibold leading-tight tracking-tight text-text-primary">
      {title}
    </h4>
    <div className="mt-2.5">
      <StatusLine tone={tone}>{status}</StatusLine>
    </div>
    {sections.map((section) => (
      <div key={section.label} className="mt-7">
        <DetailLabel>{section.label}</DetailLabel>
        <div className="mt-3">{section.content}</div>
      </div>
    ))}
  </section>
);

/**
 * Two-up lane card. The outer border and the vertical rule between lanes are
 * the only separators - the detail groups are separated by spacing alone, no
 * rules. Shared by the SBTi claim comparison and the compliance comparison.
 */
const LaneComparison: React.FC<{ lanes: Lane[] }> = ({ lanes }) => (
  <div className="overflow-hidden rounded-xl border border-border-ui bg-surface-card">
    <div className="grid grid-cols-1 md:grid-cols-2">
      {lanes.map((lane, index) => (
        <div
          key={lane.title}
          className={`min-w-0 ${index > 0 ? 'border-t border-border-ui md:border-l md:border-t-0' : ''}`}
        >
          <LaneCard {...lane} />
        </div>
      ))}
    </div>
  </div>
);

export default LaneComparison;
