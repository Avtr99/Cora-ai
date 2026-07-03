/**
 * Country name normalization + centroid coordinates for ProjectMap.
 *
 * Our project data uses common country names (e.g., "United States", "DRC",
 * "Türkiye", "Viet Nam"). The world-atlas TopoJSON uses its own canonical
 * set (e.g., "United States of America", "Dem. Rep. Congo", "Turkey",
 * "Vietnam").
 *
 * For small countries / territories the TopoJSON omits (Singapore, Hong Kong,
 * Bahrain, Mauritius, Comoros, Cape Verde, Aruba, Guam …) we hardcode a
 * centroid so markers can still land somewhere sensible.
 */

/**
 * Data-country-name → TopoJSON-country-name mapping.
 *
 * Most entries map a data alias to a different TopoJSON name, but identity
 * entries (e.g. 'Turkey': 'Turkey') are retained intentionally: they act as
 * a whitelist of canonical TopoJSON names that getTopoName() can return
 * directly, making the set of valid TopoJSON names explicit and searchable.
 */
export const DATA_TO_TOPO_NAME: Record<string, string> = {
  'United States': 'United States of America',
  'DRC': 'Dem. Rep. Congo',
  'Democratic Republic of the Congo': 'Dem. Rep. Congo',
  'Congo, Dem. Rep.': 'Dem. Rep. Congo',
  'Türkiye': 'Turkey',
  'Turkey': 'Turkey',
  'Viet Nam': 'Vietnam',
  'Vietnam': 'Vietnam',
  'Russia': 'Russia',
  'Russian Federation': 'Russia',
  'South Korea': 'South Korea',
  'Korea, Republic of': 'South Korea',
  'North Korea': 'North Korea',
  'Bosnia and Herzegovina': 'Bosnia and Herz.',
  'North Macedonia': 'Macedonia',
  'Czechia': 'Czechia',
  'Czech Republic': 'Czechia',
  'Eswatini': 'eSwatini',
  'Swaziland': 'eSwatini',
  'Ivory Coast': "Côte d'Ivoire",
  "Cote d'Ivoire": "Côte d'Ivoire",
  "Côte d'Ivoire": "Côte d'Ivoire",
  'Laos': 'Laos',
  "Lao People's Democratic Republic": 'Laos',
  'Syria': 'Syria',
  'Syrian Arab Republic': 'Syria',
  'Central African Republic': 'Central African Rep.',
  'Dominican Republic': 'Dominican Rep.',
  'Equatorial Guinea': 'Eq. Guinea',
  'South Sudan': 'S. Sudan',
  'Western Sahara': 'W. Sahara',
  'Tanzania, United Republic of': 'Tanzania',
  'United Kingdom': 'United Kingdom',
};

/**
 * Hard-coded centroids [longitude, latitude] for countries that either
 * don't exist in the 110m TopoJSON (small islands, territories) or that we
 * want to override for visual clarity. Used as fallback when we can't find
 * a TopoJSON centroid.
 */
export const MANUAL_CENTROIDS: Record<string, [number, number]> = {
  // Override for France (Natural Earth centroid includes overseas territories, putting it in the ocean)
  'France': [2.2137, 46.2276],
  
  // Missing from 110m TopoJSON
  'Singapore': [103.8, 1.35],
  'Hong Kong': [114.17, 22.32],
  'Bahrain': [50.55, 26.07],
  'Mauritius': [57.55, -20.35],
  'Comoros': [43.87, -11.88],
  'Cape Verde': [-23.6, 15.12],
  'Aruba': [-69.97, 12.52],
  'Guam': [144.79, 13.44],
  'Malta': [14.45, 35.9],
  'Maldives': [73.22, 3.2],
  'Bahamas': [-77.4, 25.03],
  'Jamaica': [-77.3, 18.1],
  'Trinidad and Tobago': [-61.22, 10.69],
  'Puerto Rico': [-66.6, 18.2],
  'Saint Lucia': [-61.0, 13.9],
  'Barbados': [-59.5, 13.19],
  'Seychelles': [55.49, -4.68],
  'Fiji': [178.06, -17.71],
  'Samoa': [-172.1, -13.76],
  'Vanuatu': [166.96, -15.38],
  'Tonga': [-175.2, -21.18],
  'Timor-Leste': [125.73, -8.87],
  'Kiribati': [-157.35, 1.87],
  // Additional / alt names that may appear in data
  'International': [0, 20],
  'Palestine': [35.23, 31.95],
  'Kosovo': [20.9, 42.6],
};

/** Normalize a data country name to the name used in the TopoJSON. */
export function getTopoName(dataCountry: string | undefined | null): string | null {
  if (!dataCountry) return null;
  const trimmed = dataCountry.trim();
  if (DATA_TO_TOPO_NAME[trimmed]) return DATA_TO_TOPO_NAME[trimmed];
  return trimmed;
}

/** True when this country should never highlight a TopoJSON polygon. */
export function isMetaCountry(name: string | undefined | null): boolean {
  if (!name) return true;
  return name.trim().toLowerCase() === 'international';
}
