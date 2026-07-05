export interface SDG {
  number: number;
  title: string;
  bgColor: string;
  minWidth: number;
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
  statistics: Statistics;
  benefits: Benefit[];
  /** Keywords for matching queries to relevant project recommendations */
  keywords: string[];
}
