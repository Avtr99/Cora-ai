import React from 'react';
import { CASE_STUDY } from '@/lib/colors';

interface ProjectDetailsProps {
  type: string;
  location: string;
  duration: string;
  reductionRemoval?: string;
  methodology: string;
  about: string;
  mapImage?: string;
  mapImageSrcSet?: string;
  mapImageSizes?: string;
  mapSource?: string;
  projectImages?: string[];
}

/**
 * Component to display project details including type, location, duration and methodology
 * Matches the Figma design with proper styling and layout
 */
export const ProjectDetails = ({
  type,
  location,
  duration,
  reductionRemoval,
  methodology,
  about,
  mapImage,
  mapImageSrcSet,
  mapSource,
  mapImageSizes,
  projectImages,
}: ProjectDetailsProps) => {
  const hasMap = !!mapImage;

  return (
    <div className="mb-16">
      {/* Type badge */}
      <div className="mb-8">
        <span
          className="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-semibold font-inter"
          style={{ backgroundColor: CASE_STUDY.type.bg, color: CASE_STUDY.type.text }}
        >
          {type ?? '—'}
        </span>
      </div>

      {hasMap ? (
        /* Two-column layout when map exists */
        <div className="flex flex-col lg:flex-row gap-10 justify-between">
          {/* Map Image */}
          <div className="w-full lg:w-[55%] flex flex-col gap-3">
            <div className="relative aspect-[4/3] md:aspect-auto md:h-[318px] overflow-hidden rounded-xl bg-surface-subtle">
              <img
                src={mapImage}
                srcSet={mapImageSrcSet}
                sizes={mapImageSizes}
                alt="Project location map"
                className="w-full h-full object-cover"
                loading="lazy"
                decoding="async"
                width="660"
                height="318"
              />
            </div>
            {mapSource && (
              <div className="font-inter text-xs leading-[17px] text-text-muted">
                Source: {mapSource}
              </div>
            )}
          </div>

          {/* Details */}
          <div className="w-full lg:w-[40%] flex flex-col gap-8 md:gap-10">
            <DetailItem label="Project Location" value={location} />
            <DetailItem label="Project Duration" value={duration} />
            <div className="flex flex-wrap gap-6">
              <DetailItem label="Reduction / Removal" value={reductionRemoval ?? 'Both'} />
              <DetailItem label="Methodology" value={methodology} />
            </div>
          </div>
        </div>
      ) : (
        /* Full-width grid when no map */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
          <DetailItem label="Project Location" value={location} />
          <DetailItem label="Project Duration" value={duration} />
          <DetailItem label="Reduction / Removal" value={reductionRemoval ?? 'Both'} />
          <DetailItem label="Methodology" value={methodology} />
        </div>
      )}

      {/* About — full width or row with project images */}
      {projectImages && projectImages.length > 0 ? (
        <div className="mt-10 flex flex-col lg:flex-row gap-8">
          <div className="lg:w-[40%]">
            <p className="text-xs uppercase text-text-muted font-inter font-semibold leading-[17px] mb-3">About</p>
            <p className="font-inter text-sm md:text-base text-text-secondary leading-[1.7]">
              {about ?? '—'}
            </p>
          </div>
          <div className="lg:w-[60%] grid grid-cols-1 sm:grid-cols-2 gap-4">
            {projectImages.map((img, i) => (
              <div key={i} className="relative aspect-[4/3] overflow-hidden rounded-xl bg-surface-subtle border border-border-ui shadow-sm">
                <img
                  src={img}
                  alt={`Project image ${i + 1}`}
                  className="w-full h-full object-cover"
                  loading="lazy"
                  decoding="async"
                />
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="mt-10">
          <p className="text-xs uppercase text-text-muted font-inter font-semibold leading-[17px] mb-3">About</p>
          <p className="font-inter text-sm md:text-base text-text-secondary leading-[1.7] max-w-[900px]">
            {about ?? '—'}
          </p>
        </div>
      )}
    </div>
  );
};

/** Reusable detail row for consistent styling */
const DetailItem = ({ label, value }: { label: string; value?: string }) => (
  <div className="flex flex-col">
    <p className="text-xs uppercase text-text-muted font-inter font-semibold leading-[14px] mb-2">{label}</p>
    <p className="font-inter text-sm font-medium text-text-primary leading-[17px]">{value ?? '—'}</p>
  </div>
);

ProjectDetails.displayName = 'ProjectDetails';
