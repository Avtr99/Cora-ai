/**
 * IconWrapper Component
 * 
 * Lightweight wrapper for SVGR-generated icon components
 * Provides consistent API and styling across the application
 * 
 * IMPORTANT: All icons are stroke-based (outline), not fill-based (solid)
 * This component applies `stroke` and sets `fill="none"`
 * 
 * Accessibility:
 * - Use `title` for meaningful icons that convey information
 * - Use `aria-hidden={true}` for purely decorative icons
 * - Do NOT use both together (component will throw an error in development and prioritize title)
 * 
 * Usage:
 * import ChatIcon from '@/assets/icons/chat.svg?react';
 * 
 * // Accessible icon with title
 * <IconWrapper Icon={ChatIcon} size={24} title="Chat" />
 * 
 * // Decorative icon (hidden from screen readers)
 * <IconWrapper Icon={ChatIcon} size={24} aria-hidden={true} />
 * 
 * // With state-based colors
 * <IconWrapper Icon={ChatIcon} size={24} state="active" aria-hidden={true} />
 */

import React, { useMemo } from 'react';
import { SVGProps } from 'react';
import { ICON_STATE } from '@/lib/colors';

export type IconState = 'default' | 'active' | 'selected';

export interface IconWrapperProps {
  /** SVGR-generated icon component */
  Icon: React.FC<SVGProps<SVGSVGElement>>;
  
  /** Size in pixels (default: 24) */
  size?: number;
  
  /** Custom color (overrides state-based colors) */
  color?: string;
  
  /** State-based color selection */
  state?: IconState;
  
  /** Additional CSS classes */
  className?: string;
  
  /** Accessible title for screen readers (use for meaningful icons) */
  title?: string;
  
  /** Hide from screen readers (use for decorative icons) */
  'aria-hidden'?: boolean;
  
  /** Click handler */
  onClick?: () => void;
  
  /** Additional SVG props */
  svgProps?: Omit<SVGProps<SVGSVGElement>, 'width' | 'height' | 'fill' | 'className'>;
}

/**
 * State-based color mapping
 * Matches previous Icon component behavior
 */
const STATE_COLORS: Record<IconState, string> = {
  default: ICON_STATE.default,
  active: ICON_STATE.active,
  selected: ICON_STATE.selected,
};

export const IconWrapper: React.FC<IconWrapperProps> = ({
  Icon,
  size = 24,
  color,
  state = 'default',
  className = '',
  title,
  'aria-hidden': ariaHidden,
  onClick,
  svgProps = {},
}) => {
  // Detect accessibility conflict: title and aria-hidden should not both be set
  if (process.env.NODE_ENV !== 'production' && title && ariaHidden) {
    throw new Error(
      'IconWrapper: Both "title" and "aria-hidden" props were provided. ' +
      'This creates an accessibility conflict. An icon cannot be both meaningful (title) and decorative (aria-hidden). ' +
      'Please provide only one of these props.'
    );
  }

  // Resolve conflict: if title is present, icon should be accessible (not hidden)
  const shouldHide = title ? false : ariaHidden === true;
  const computedRole = title ? 'img' : shouldHide ? 'presentation' : undefined;

  // Determine final color (explicit color overrides state-based color)
  const finalColor = color || STATE_COLORS[state];

  // Create a unique ID for this instance to scope the styles
  const wrapperId = React.useId().replace(/:/g, '_');

  // Extract style from svgProps to merge it
  const { style: userStyle, ...svgRest } = svgProps;

  return (
    <>
      <style>{`
        .icon-wrapper-${wrapperId} svg path,
        .icon-wrapper-${wrapperId} svg circle,
        .icon-wrapper-${wrapperId} svg line,
        .icon-wrapper-${wrapperId} svg polyline,
        .icon-wrapper-${wrapperId} svg rect,
        .icon-wrapper-${wrapperId} svg polygon {
          stroke: ${finalColor} !important;
        }
      `}</style>
      <span
        className={`icon-wrapper-${wrapperId} ${className}`}
        onClick={onClick}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: size,
          height: size,
          color: finalColor,
        }}
      >
        <Icon
          width={size}
          height={size}
          fill="none"
          aria-label={title}
          aria-hidden={shouldHide || undefined}
          role={computedRole}
          style={{ display: 'block', ...userStyle }}
          {...svgRest}
        />
      </span>
    </>
  );
};

// Re-export types for convenience
export type { SVGProps };
