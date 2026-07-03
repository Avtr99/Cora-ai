/**
 * Centralized color tokens for the application.
 * Extends the design system defined in docs/DESIGN_TOKENS_REFERENCE.md.
 *
 * Brand tokens, status colors, and project-type semantic colors
 * all live here so components import from one place.
 */

// ---------------------------------------------------------------------------
// Brand tokens (mirrors DESIGN_TOKENS_REFERENCE.md)
// ---------------------------------------------------------------------------
export const BRAND = {
  primary900: '#403D85',
  primary700: '#4A2AA3',
  primary500: '#6F4ECB',
  primary200: '#E9D5FF',
  primary100: '#F3E8FF',
  primary50: '#FAF5FF',
} as const;

// ---------------------------------------------------------------------------
// Neutral scale & surfaces
// ---------------------------------------------------------------------------
export const NEUTRAL = {
  0: '#FFFFFF',
  25: '#FAFAFA',
  50: '#F8F9FA',
  100: '#F3F4F6',
  150: '#E5E7EB',
  200: '#D6D6D6',
  300: '#B8BEC8',
  400: '#6B7280',
  600: '#4B5563',
  800: '#525252',
  900: '#171717',
} as const;

// ---------------------------------------------------------------------------
// Text tokens (aliases for semantic usage)
// ---------------------------------------------------------------------------
export const TEXT = {
  primary: '#171717',
  body: '#525252',
  muted: '#6B7280',
  disabled: '#B8BEC8',
  inverse: '#FFFFFF',
} as const;

// ---------------------------------------------------------------------------
// Interactive state colors
// ---------------------------------------------------------------------------
export const INTERACTIVE = {
  default: '#6B7280',
  hover: BRAND.primary500,
  active: BRAND.primary500,
  disabled: '#B8BEC8',
  focusRing: 'rgba(74,42,163,0.35)',
  focusRingLight: 'rgba(74,42,163,0.25)',
} as const;

// ---------------------------------------------------------------------------
// Icon state colors (used by IconWrapper component)
// ---------------------------------------------------------------------------
export const ICON_STATE = {
  default: '#6B7280',
  active: BRAND.primary500,
  selected: BRAND.primary500,
} as const;

// ---------------------------------------------------------------------------
// Project-type semantic colors
// Accent  = left-border / header stripe (not currently used after cleanup)
// Bg      = badge/pill background
// Text    = badge/pill foreground
// ---------------------------------------------------------------------------
export type TypeColorSet = { accent: string; bg: string; text: string };

const TYPE_COLOR_MAP: Record<string, TypeColorSet> = {
  forest:          { accent: '#2D6A4F', bg: '#ECFDF5', text: '#065F46' },
  redd:            { accent: '#2D6A4F', bg: '#ECFDF5', text: '#065F46' },
  afforestation:   { accent: '#2D6A4F', bg: '#ECFDF5', text: '#065F46' },
  reforestation:   { accent: '#2D6A4F', bg: '#ECFDF5', text: '#065F46' },
  mangrove:        { accent: '#2D6A4F', bg: '#ECFDF5', text: '#065F46' },
  'blue carbon':   { accent: '#1D4E89', bg: '#EFF6FF', text: '#1E40AF' },
  renewable:       { accent: '#1D4E89', bg: '#EFF6FF', text: '#1E40AF' },
  solar:           { accent: '#1D4E89', bg: '#EFF6FF', text: '#1E40AF' },
  wind:            { accent: '#1D4E89', bg: '#EFF6FF', text: '#1E40AF' },
  hydro:           { accent: '#1D4E89', bg: '#EFF6FF', text: '#1E40AF' },
  biomass:         { accent: '#1D4E89', bg: '#EFF6FF', text: '#1E40AF' },
  geothermal:      { accent: '#1D4E89', bg: '#EFF6FF', text: '#1E40AF' },
  energy:          { accent: '#1D4E89', bg: '#EFF6FF', text: '#1E40AF' },
  agriculture:     { accent: '#9A6C38', bg: '#FFFBEB', text: '#92400E' },
  soil:            { accent: '#9A6C38', bg: '#FFFBEB', text: '#92400E' },
  livestock:       { accent: '#9A6C38', bg: '#FFFBEB', text: '#92400E' },
  rice:            { accent: '#9A6C38', bg: '#FFFBEB', text: '#92400E' },
  cookstove:       { accent: '#B85C38', bg: '#FFF7ED', text: '#9A3412' },
  household:       { accent: '#B85C38', bg: '#FFF7ED', text: '#9A3412' },
  stove:           { accent: '#B85C38', bg: '#FFF7ED', text: '#9A3412' },
  water:           { accent: '#B85C38', bg: '#FFF7ED', text: '#9A3412' },
  biogas:          { accent: '#B85C38', bg: '#FFF7ED', text: '#9A3412' },
  landfill:        { accent: '#5A6577', bg: '#F1F5F9', text: '#334155' },
  waste:           { accent: '#5A6577', bg: '#F1F5F9', text: '#334155' },
  industrial:      { accent: '#5A6577', bg: '#F1F5F9', text: '#334155' },
  cement:          { accent: '#5A6577', bg: '#F1F5F9', text: '#334155' },
  ozone:           { accent: '#5A6577', bg: '#F1F5F9', text: '#334155' },
  fugitive:        { accent: '#5A6577', bg: '#F1F5F9', text: '#334155' },
  methane:         { accent: '#5A6577', bg: '#F1F5F9', text: '#334155' },
  transport:       { accent: '#5A6577', bg: '#F1F5F9', text: '#334155' },
  chemical:        { accent: '#5A6577', bg: '#F1F5F9', text: '#334155' },
  sf6:             { accent: '#5A6577', bg: '#F1F5F9', text: '#334155' },
  n2o:             { accent: '#5A6577', bg: '#F1F5F9', text: '#334155' },
  hfc:             { accent: '#5A6577', bg: '#F1F5F9', text: '#334155' },
};

const DEFAULT_TYPE_COLOR: TypeColorSet = {
  accent: BRAND.primary500,
  bg: '#EDE9FE',  // Slightly deeper purple for better contrast on selection
  text: '#5B21B6',
};

/**
 * Returns the semantic color set for a project type string.
 * Matches against keywords (case-insensitive).
 */
export function getProjectTypeColor(type: string | undefined): TypeColorSet {
  if (!type) return DEFAULT_TYPE_COLOR;
  const lower = type.toLowerCase();
  for (const [keyword, colors] of Object.entries(TYPE_COLOR_MAP)) {
    if (lower.includes(keyword)) return colors;
  }
  return DEFAULT_TYPE_COLOR;
}

// ---------------------------------------------------------------------------
// Status badge colors
// ---------------------------------------------------------------------------
export type StatusColorSet = { bg: string; text: string; dot: string };

const STATUS_STYLES: Record<string, StatusColorSet> = {
  registered:               { bg: '#ECFDF5', text: '#065F46', dot: '#10B981' },
  active:                   { bg: '#ECFDF5', text: '#065F46', dot: '#10B981' },
  completed:                { bg: '#EFF6FF', text: '#1E40AF', dot: '#3B82F6' },
  cancelled:                { bg: '#FEF2F2', text: '#991B1B', dot: '#EF4444' },
  canceled:                 { bg: '#FEF2F2', text: '#991B1B', dot: '#EF4444' },
  'under development':      { bg: '#FFFBEB', text: '#92400E', dot: '#F59E0B' },
  'under validation':       { bg: '#FFFBEB', text: '#92400E', dot: '#F59E0B' },
  'crediting period ended': { bg: '#F3F4F6', text: '#4B5563', dot: '#9CA3AF' },
};

const DEFAULT_STATUS_STYLE: StatusColorSet = {
  bg: '#F3F4F6',
  text: '#4B5563',
  dot: '#9CA3AF',
};

/** Returns the badge color set for a project status string. */
export function getStatusStyle(status: string | undefined | null): StatusColorSet {
  if (!status) return DEFAULT_STATUS_STYLE;
  return STATUS_STYLES[status.toLowerCase()] ?? DEFAULT_STATUS_STYLE;
}

// ---------------------------------------------------------------------------
// Case-study semantic colors (lens labels, type badges, chips)
// ---------------------------------------------------------------------------
export const CASE_STUDY = {
  lens:    { bg: '#E2EFD2', text: '#496731' },
  type:    { bg: '#F3F6FF', text: '#4F46E5' },
  rating:  { bg: '#F3F4F6', text: '#4B5563' },
} as const;

export const CHIP = {
  positive: { bg: '#DFFDD6', text: '#171717' },
  info:     { bg: '#B4DBFF', text: '#171717' },
  neutral:  { bg: '#F3F4F6', text: '#171717' },
} as const;

export const FEEDBACK = {
  success: '#61CA78',
} as const;

// ---------------------------------------------------------------------------
// Category themes (Pricing page)
// ---------------------------------------------------------------------------
export type CategoryThemeSet = { iconColor: string; iconBgColor: string; textColor: string };

export const CATEGORY_THEMES: Record<string, CategoryThemeSet> = {
  agriculture:       { iconColor: '#294C7B', iconBgColor: '#DBEAFE', textColor: '#294C7B' },
  'household devices': { iconColor: '#6F4ECB', iconBgColor: '#F3E8FF', textColor: '#403D85' },
  'renewable energy':  { iconColor: '#BF7E2B', iconBgColor: '#F9DBB6', textColor: '#A65B00' },
  'redd+':             { iconColor: '#A13D15', iconBgColor: '#FAD1C1', textColor: '#A13D15' },
} as const;

/**
 * Returns the theme colors for a pricing category.
 * Matches against keywords (case-insensitive).
 */
export function getCategoryTheme(category: string | undefined): CategoryThemeSet {
  if (!category) return CATEGORY_THEMES.agriculture;
  const lower = category.toLowerCase();
  for (const [keyword, colors] of Object.entries(CATEGORY_THEMES)) {
    if (lower.includes(keyword)) return colors;
  }
  return CATEGORY_THEMES.agriculture;
}

// ---------------------------------------------------------------------------
// Notice/Alert card colors
// ---------------------------------------------------------------------------
export type NoticeColorSet = { bg: string; border: string; text: string; iconBg?: string; iconBorder?: string };

export const NOTICE_COLORS = {
  research: {
    bg: '#FFFBEB',
    border: '#FEF3C7',
    text: '#92400E',
    iconBg: '#FEF3C7',
    iconBorder: '#FDE68A',
  },
  privacy: {
    bg: '#F5F3FF',
    border: '#EDE9FE',
    text: '#5B21B6',
    iconBg: '#EDE9FE',
    iconBorder: '#DDD6FE',
  },
  cancelled: {
    bg: '#F3F0FF',
    border: '#DAD6FF',
    text: '#2F2A72',
  },
  error: {
    bg: '#FEF2F2',
    border: '#FECACA',
    text: '#991B1B',
  },
} as const;

// ---------------------------------------------------------------------------
// Choropleth density colors (shared by ProjectMap + MapLegend)
// CHOROPLETH_COLORS is ordered from darkest/highest threshold to
// faintest/lowest threshold (descending by `min`).
// ---------------------------------------------------------------------------
export const CHOROPLETH_COLORS: ReadonlyArray<{ min: number; color: string }> = [
  { min: 500, color: NEUTRAL[300] },
  { min: 100, color: NEUTRAL[200] },
  { min: 10,  color: NEUTRAL[150] },
  { min: 1,   color: NEUTRAL[100] },
];

// ---------------------------------------------------------------------------
// Trend colors (SBTImpact component)
// Consistent nested structure: each trend has badge and icon sub-objects
// ---------------------------------------------------------------------------
export type TrendBadgeColorSet = { bg: string; text: string; border?: string };
export type TrendIconColorSet = { bg: string; color: string };
export type TrendColorSet = { badge: TrendBadgeColorSet; icon: TrendIconColorSet };

export const TREND_COLORS = {
  rising: {
    badge: { bg: '#E3F6D6', text: '#2F4F2F' },
    icon: { bg: '#E8F5E0', color: '#57924E' },
  },
  declining: {
    badge: { bg: '#FDE6C9', text: '#7C2D00' },
    icon: { bg: '#FFE8CC', color: '#A65B00' },
  },
  note: {
    badge: { bg: '#FFFBF0', border: '#F5E6C3', text: '#92400E' },
    icon: { bg: '#FEF3C7', color: '#D97706' },
  },
} as const satisfies Record<'rising' | 'declining' | 'note', TrendColorSet>;

// ---------------------------------------------------------------------------
// Semantic status colors (success / error / warning / info)
// Used for alerts, banners, badges, validation states, and icon containers.
// ---------------------------------------------------------------------------
export type SemanticColorSet = {
  bg: string;
  text: string;
  border: string;
  icon: string;
  iconBg: string;
  button: string;
  buttonHover: string;
};

export const SEMANTIC: Record<'success' | 'error' | 'warning' | 'info', SemanticColorSet> = {
  success: {
    bg: '#ECFDF5',
    text: '#065F46',
    border: '#D1FAE5',
    icon: '#10B981',
    iconBg: '#ECFDF5',
    button: '#047857',
    buttonHover: '#065F46',
  },
  error: {
    bg: '#FEF2F2',
    text: '#991B1B',
    border: '#FECACA',
    icon: '#EF4444',
    iconBg: '#FEF2F2',
    button: '#B91C1C',
    buttonHover: '#991B1B',
  },
  warning: {
    bg: '#FFFBEB',
    text: '#92400E',
    border: '#FEF3C7',
    icon: '#F59E0B',
    iconBg: '#FEF3C7',
    button: '#B45309',
    buttonHover: '#92400E',
  },
  info: {
    bg: '#EFF6FF',
    text: '#1E40AF',
    border: '#BFDBFE',
    icon: '#3B82F6',
    iconBg: '#EFF6FF',
    button: '#1D4ED8',
    buttonHover: '#1E40AF',
  },
} as const;

// ---------------------------------------------------------------------------
// Chart / data-visualization colors
// ---------------------------------------------------------------------------
export const CHART = {
  household: '#4F46E5',
  agriculture: '#2098D8',
  renewable: '#F59E0B',
  redd: '#EF4444',
} as const;

// ---------------------------------------------------------------------------
// KPI / methodology split colors (Projects page)
// ---------------------------------------------------------------------------
export const KPI = {
  reduction: '#C4627A',
  removal: '#2D9D78',
  other: '#6B7280',
} as const;

// ---------------------------------------------------------------------------
// Gauge chart colors (case-study ProjectStatistics)
// ---------------------------------------------------------------------------
export const GAUGE = {
  retired: '#4F46E5',
  remaining: '#10B981',
} as const;
