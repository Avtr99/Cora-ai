/**
 * TypeScript types for the VCM Project Comparison feature.
 * Two-tier structure: top-level fields power cards/filters/search,
 * _detail holds all remaining fields for drawer/compare views.
 */

export interface VCMProjectDetail {
  methodology: string;
  methodologyVersion: string;
  state: string;
  siteLocation: string;
  developer: string;
  owner: string;
  operator: string;
  designee: string;
  verifier: string;
  bufferPool: number;
  annualReductions: number;
  pers: number;
  arbWaProject: string;
  arbWaStatus: string;
  arbWaId: string;
  registryArbWa: string;
  poaId: string;
  poaStatus: string;
  listed: string;
  registered: string;
  firstIssuanceYear: string;
  certifications: string;
  registryType: string;
  registryDocs: string;
  projectWebsite: string;
  description: string;
  registryNotes: string;
  berkeleyNotes: string;
}

export interface VCMProject {
  id: string;
  name: string;
  registry: string;
  status: string;
  scope: string;
  type: string;
  reductionRemoval: string;
  country: string;
  region: string;
  creditsIssued: number;
  creditsRetired: number;
  creditsRemaining: number;
  /** Promoted from _detail for search without loading detail file */
  developer?: string;
  /** Only present when detail data has been loaded */
  _detail?: VCMProjectDetail;
}

export interface ProjectsData {
  lastUpdated: string;
  version: string;
  totalCount: number;
  projects: VCMProject[];
}

/** Filter keys that correspond to top-level string fields on VCMProject */
export type ProjectFilterKey =
  | 'scope'
  | 'type'
  | 'region'
  | 'country'
  | 'registry'
  | 'status'
  | 'reductionRemoval';

/** Shape of active filters — key absent (undefined) means "all"; present string is the selected value */
export type ProjectFilters = Partial<Record<ProjectFilterKey, string>>;

/** Returns a readonly tuple whose elements are validated as keys of T */
const makeKeyTuple = <T>() =>
  <const K extends readonly (keyof T & string)[]>(...keys: K): K => keys;

/** Fields searched by the substring search (developer promoted from _detail) */
export const SEARCH_FIELDS = makeKeyTuple<VCMProject>()('name', 'id', 'country', 'type', 'developer');
