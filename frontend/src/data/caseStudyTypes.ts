export interface SDG {
  number: number;
  title: string;
}

export interface Strength {
  text: string;
}

export interface PermanenceRisk {
  percentage: number;
  label: string;
}

export interface Benefit {
  number: number;
  title: string;
  description: string;
}

export interface Statistics {
  carbonSequestered: string;
  bufferPool: string;
  creditsIssued: string;
  creditsRetired: string;
  source: string;
  permanenceRisk: PermanenceRisk;
}

export interface BeforeAfterImage {
  before: string;
  after: string;
  beforeLabel?: string;
  afterLabel?: string;
  caption?: string;
  attribution?: string;
}

export interface OverviewMapImage {
  image: string;
  caption?: string;
  attribution?: string;
}

export interface CaseStudyData {
  id: string;
  title: string;
  organization: string;
  organizationId: string;
  registry: string;
  registryUrl: string;
  tags: string[];
  lensLabel: string;
  mainImage: string;
  mainImageSrcSet?: string;
  mainImageCaption?: string;
  strengths: Strength[];
  sdgs: SDG[];
  rating: string;
  ratingAgency: string;
  ratingNote: string;
  projectType: string;
  location: string;
  duration: string;
  reductionRemoval: string;
  methodology: string;
  about: string;
  summary: string;
  mapImage?: string;
  mapImageSrcSet?: string;
  mapImageSizes?: string;
  mapSource?: string;
  projectImages?: string[];
  galleryImages?: string[];
  /** Locator/overview map shown in the project details section. */
  overviewMap?: OverviewMapImage;
  /** Side-by-side before/after satellite images (e.g., per village). */
  beforeAfterImages?: BeforeAfterImage[];
  statistics: Statistics;
  benefits: Benefit[];
  /** Keywords for matching queries to relevant project recommendations */
  keywords: string[];
}
