/**
 * Shared constants and pure helpers for the project map.
 * Centralised here so sub-components and hooks can import without
 * duplicating magic numbers or colour logic.
 */
import React from 'react';
import { CHOROPLETH_COLORS, NEUTRAL } from '@/lib/colors';

export const MAP_WIDTH = 800;
export const MAP_HEIGHT = 420;

// Number of top countries that receive a scope-coloured marker on top of the
// choropleth. The bubbles carry the density signal, so the choropleth can
// stay intentionally quiet and most countries still get a visible dot.
export const TOP_N_MARKERS = 40;

// Bubble radius envelope in px (post-projection). Small enough not to crowd
// neighbours at zoom 1, large enough to spot at a glance for big producers.
export const BUBBLE_MIN_R = 3.2;
export const BUBBLE_MAX_R = 9.5;

// Region names that the disputed-areas dataset tags separately but which
// should be treated as part of India for project aggregation.
export const DISPUTED_REGION_NAMES = [
  'Jammu and Kashmir',
  'Aksai Chin',
  'Gilgit-Baltistan',
  'Shaksam Valley',
  'Demchok',
  'Samdu Valleys',
  'Tirpani Valleys',
  'Bara Hotii Valleys',
  'Siachen Glacier',
  'Junagadh and Manavadar', // Excluded from rendering
];

// Choropleth scale — soft monochrome ramp
export const CHOROPLETH_SCALE = CHOROPLETH_COLORS;
export const NO_DATA_FILL = `${NEUTRAL[50]}eb`;    // Soft off-white for empty land
export const HOVER_FILL_DATA = NEUTRAL[400];        // Neutral 400
export const HOVER_FILL_EMPTY = NEUTRAL[100];      // Neutral 100
export const SELECTED_FILL = NEUTRAL[400];          // Neutral 400
export const SELECTED_STROKE = `${NEUTRAL[0]}df`;
export const HOVER_STROKE = NEUTRAL[200];           // Neutral 200

// Disputed area overlay stroke colors (dashed boundaries)
export const DISPUTED_STROKE_DEFAULT = NEUTRAL[200];        // Neutral 200
export const DISPUTED_STROKE_SELECTED = NEUTRAL[0];
export const DISPUTED_STROKE_HOVER = NEUTRAL[300];
export const DISPUTED_STROKE_HOVER_SELECTED = `${NEUTRAL[0]}df`;

// Zoom level we snap to when the user focuses on a country (click or list
// select). Low enough to preserve regional context, high enough to feel
// like a real "focus".
export const FOCUS_ZOOM = 3;
export const DEFAULT_CENTER: [number, number] = [10, 15];

// Pre-sorted descending by min for highest-bucket-first matching
const SORTED_CHOROPLETH_SCALE = [...CHOROPLETH_SCALE].sort((a, b) => b.min - a.min);

/** Pick the choropleth fill colour for a given project count.
 *  Defensively handles any order of CHOROPLETH_SCALE by iterating the
 *  module-level pre-sorted copy.
 */
export function getChoroplethFill(count: number): string {
  for (const b of SORTED_CHOROPLETH_SCALE) {
    if (count >= b.min) return b.color;
  }
  return NO_DATA_FILL;
}

/** Extract mouse coordinates from a Framer Motion event (which is typed as
 *  `unknown`) with runtime validation to ensure caller receives valid values.
 */
export function getMouseCoords(e: unknown): { clientX: number; clientY: number; stopPropagation: () => void } {
  const me = e as React.MouseEvent;
  if (
    typeof me?.clientX !== 'number' ||
    typeof me?.clientY !== 'number' ||
    typeof me?.stopPropagation !== 'function'
  ) {
    throw new Error('getMouseCoords: Invalid mouse event - missing clientX/clientY or stopPropagation');
  }
  return { clientX: me.clientX, clientY: me.clientY, stopPropagation: () => me.stopPropagation() };
}
