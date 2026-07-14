import React from 'react';
import {
  ReactCompareSlider,
  ReactCompareSliderHandle,
  ReactCompareSliderImage,
} from 'react-compare-slider';

import type { BeforeAfterImage } from '@/data/caseStudyTypes';

const HANDLE_STYLE: React.CSSProperties = {
  '--rcs-handle-color': 'rgba(255, 255, 255, 0.92)',
} as React.CSSProperties;

const HANDLE_BUTTON_STYLE: React.CSSProperties = {
  width: '2.25rem',
  height: '2.25rem',
  gap: '0.25rem',
  borderWidth: 1,
  backgroundColor: 'rgba(7, 22, 18, 0.72)',
  borderColor: 'rgba(255, 255, 255, 0.40)',
  backdropFilter: 'blur(4px)',
  WebkitBackdropFilter: 'blur(4px)',
  boxShadow: '0 1px 4px rgba(0, 0, 0, 0.28)',
};

const HANDLE_LINES_STYLE: React.CSSProperties = {
  width: 1,
  opacity: 0.85,
  boxShadow: '0 0 2px rgba(0, 0, 0, 0.4)',
};

interface BeforeAfterSliderProps extends BeforeAfterImage {
  /** Aspect ratio tailwind class for the slider container. */
  aspectClass?: string;
}

/**
 * Accessible before/after image comparison slider.
 *
 * Uses react-compare-slider so the comparison is interactive, keyboard-navigable,
 * and works on touch devices without custom drag logic.
 */
export const BeforeAfterSlider: React.FC<BeforeAfterSliderProps> = ({
  before,
  after,
  beforeLabel = 'Before',
  afterLabel = 'After',
  caption,
  attribution,
  aspectClass = 'aspect-[4/3]',
}) => {
  return (
    <figure className="flex h-full w-full flex-col">
      <div
        className={`relative ${aspectClass} w-full overflow-hidden rounded-xl bg-surface-subtle border border-border-ui shadow-sm`}
      >
        <ReactCompareSlider
          itemOne={
            <ReactCompareSliderImage
              src={before}
              alt={beforeLabel}
              className="w-full h-full object-cover"
            />
          }
          itemTwo={
            <ReactCompareSliderImage
              src={after}
              alt={afterLabel}
              className="w-full h-full object-cover"
            />
          }
          handle={
            <ReactCompareSliderHandle
              style={HANDLE_STYLE}
              buttonStyle={HANDLE_BUTTON_STYLE}
              linesStyle={HANDLE_LINES_STYLE}
            />
          }
          defaultPosition={50}
          keyboardIncrement="5%"
          className="absolute inset-0 [&_[data-rcs='handle-root']]:focus-visible:ring-2 [&_[data-rcs='handle-root']]:focus-visible:ring-inset [&_[data-rcs='handle-root']]:focus-visible:ring-white"
        />
        <span className="absolute top-2 left-2 z-10 px-2 py-1 rounded-md text-xs font-semibold font-inter bg-black/60 text-white backdrop-blur-sm pointer-events-none">
          {beforeLabel}
        </span>
        <span className="absolute top-2 right-2 z-10 px-2 py-1 rounded-md text-xs font-semibold font-inter bg-black/60 text-white backdrop-blur-sm pointer-events-none">
          {afterLabel}
        </span>
      </div>
      {(caption || attribution) && (
        <figcaption className="mt-2 font-inter text-xs text-text-muted leading-normal">
          {caption}
          {caption && attribution && ' · '}
          {attribution}
        </figcaption>
      )}
    </figure>
  );
};

BeforeAfterSlider.displayName = 'BeforeAfterSlider';
