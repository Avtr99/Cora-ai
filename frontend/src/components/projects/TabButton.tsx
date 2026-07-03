import React from 'react';
import { motion } from 'framer-motion';
import { IconWrapper } from '@/components/icons/IconWrapper';
import { TEXT } from '@/lib/colors';

export interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon?: React.ReactNode;
  Icon?: React.FC<React.SVGProps<SVGSVGElement>>;
  iconSize?: number;
  strokeWidth?: number;
  label: string;
  disabled?: boolean;
  id?: string;
  ariaControls?: string;
  className?: string;
  // Each tab group needs its own layoutId so the sliding pill doesn't
  // fly across the screen between the inline split view's tabs and the
  // fullscreen overlay's tabs when both exist in the DOM simultaneously.
  layoutId?: string;
}

const TabButton: React.FC<TabButtonProps> = ({
  active,
  onClick,
  icon,
  Icon,
  iconSize = 12,
  strokeWidth = 1.75,
  label,
  disabled,
  id,
  ariaControls,
  className = '',
  layoutId = 'right-panel-tab-pill',
}) => {
  const iconColor = disabled ? TEXT.disabled : active ? TEXT.inverse : TEXT.muted;
  const resolvedIcon = Icon ? (
    <IconWrapper Icon={Icon} size={iconSize} color={iconColor} aria-hidden={true} svgProps={{ strokeWidth }} />
  ) : icon;
  return (
  <button
    type="button"
    role="tab"
    id={id}
    aria-controls={ariaControls}
    aria-selected={active}
    tabIndex={active ? 0 : -1}
    disabled={disabled}
    onClick={onClick}
    className={`relative inline-flex items-center gap-1.5 h-7 px-3 rounded-full font-inter text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
      ${disabled ? 'text-border-ui cursor-not-allowed' : active ? 'text-white' : 'text-text-secondary hover:text-text-primary'} ${className}`}
  >
    {active && !disabled && (
      <motion.span
        layoutId={layoutId}
        className="absolute inset-0 -z-0 bg-text-primary rounded-full"
        transition={{ type: 'spring', stiffness: 480, damping: 32 }}
      />
    )}
    <span className="relative z-10 flex-shrink-0 flex items-center">{resolvedIcon}</span>
    <span className="relative z-10">{label}</span>
  </button>
  );
};

export default TabButton;
