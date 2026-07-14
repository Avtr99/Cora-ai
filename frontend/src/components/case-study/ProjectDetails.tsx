import React from 'react';
import { CASE_STUDY } from '@/lib/colors';

interface ProjectDetailsProps {
  type: string;
  location: string;
  duration: string;
  reductionRemoval?: string;
  methodology: string;
}

/**
 * Component to display project type badge and key metadata.
 */
export function ProjectDetails({
  type,
  location,
  duration,
  reductionRemoval,
  methodology,
}: ProjectDetailsProps): JSX.Element {
  return (
    <div className="mb-16">
      <span
        className="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-semibold font-inter"
        style={{ backgroundColor: CASE_STUDY.type.bg, color: CASE_STUDY.type.text }}
      >
        {type ?? '—'}
      </span>

      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <DetailItem label="Project Location" value={location} />
        <DetailItem label="Project Duration" value={duration} />
        <DetailItem label="Reduction / Removal" value={reductionRemoval ?? 'Both'} />
        <DetailItem label="Methodology" value={methodology} />
      </div>
    </div>
  );
}

/** Reusable detail row for consistent styling */
function DetailItem({ label, value }: { label: string; value?: string }): JSX.Element {
  return (
    <div className="flex flex-col">
      <p className="text-xs uppercase text-text-muted font-inter font-semibold leading-[14px] mb-2">{label}</p>
      <p className="font-inter text-sm font-medium text-text-primary leading-[17px]">{value ?? '—'}</p>
    </div>
  );
}

ProjectDetails.displayName = 'ProjectDetails';
