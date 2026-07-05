import type { CaseStudyData } from './caseStudyTypes';

// Mangrove images
import mangroveImage from '@/assets/mangrove-restoration-image.webp';
import mangroveImage640 from '@/assets/mangrove-restoration-image-640.webp';
import mangroveImage960 from '@/assets/mangrove-restoration-image-960.webp';
import mangroveMap from '@/assets/mangrove-restoration-project-boundary.webp';
import mangroveMap480 from '@/assets/mangrove-restoration-map-480.webp';
import mangroveMap768 from '@/assets/mangrove-restoration-map-768.webp';

// Humbo images
import humboMain from '@/assets/case-studies/humbo/humbo-main.webp';
import humboMain640 from '@/assets/case-studies/humbo/humbo-main-640.webp';
import humboMain960 from '@/assets/case-studies/humbo/humbo-main-960.webp';
import humboArea from '@/assets/case-studies/humbo/humbo-area.webp';
import humboArea640 from '@/assets/case-studies/humbo/humbo-area-640.webp';
import humboArea960 from '@/assets/case-studies/humbo/humbo-area-960.webp';
import humboSign from '@/assets/case-studies/humbo/humbo-sign.webp';
import humboMap from '@/assets/case-studies/humbo/humbo-map.png';
import humboProjectBoundary from '@/assets/case-studies/humbo/humbo-project-boundary.webp';

export const caseStudies: CaseStudyData[] = [
  {
    id: 'mangrove-myanmar',
    title: 'Reforestation And Restoration Of Degraded Mangrove Lands, Sustainable Livelihood And Community Development In Myanmar',
    organization: 'Worldview International Foundation',
    organizationId: 'VCS1764',
    registry: 'Verra',
    registryUrl: 'https://registry.verra.org/app/projectDetail/VCS/1764',
    tags: ['REFORESTATION', 'CARBON CREDITS'],
    lensLabel: 'Understanding high quality credits',
    mainImage: mangroveImage,
    mainImageSrcSet: `${mangroveImage640} 640w, ${mangroveImage960} 960w, ${mangroveImage} 1025w`,
    strengths: [
      { text: 'Strong biodiversity' },
      { text: 'Verified carbon sink' },
      { text: 'Robust measures against non-permanence risks' },
      { text: 'Run by skilled, local experts, with development and livelihood in biodiversity' }
    ],
    sdgs: [
      { number: 8, title: 'Decent Work and Economic Growth', bgColor: '#A21942', minWidth: 60 },
      { number: 13, title: 'Climate Action', bgColor: '#3F7E44', minWidth: 55 },
      { number: 14, title: 'Life Below Water', bgColor: '#0A97D9', minWidth: 55 }
    ],
    rating: 'AA',
    ratingAgency: 'BeZero',
    ratingNote: 'AA - Very high likelihood of achieving 1 tonne of CO₂e avoided or removed',
    projectType: 'Mangroves restoration / Conservation',
    location: '16 villages in Ayeyarwady Region in Myanmar',
    duration: '2018 to 2048',
    reductionRemoval: 'Both',
    methodology: 'AR-AMS004',
    about: 'Restoring the degraded mangrove landscape covering 2,065 ha. It involves planting about 9.1 million mangrove trees in the Magu, Thabaung, and Thaegone village tracts.',
    summary: 'Restoring 2,065 ha of degraded mangrove landscape. 9.1 million trees planted across 16 villages in Myanmar\'s Ayeyarwady Region.',
    mapImage: mangroveMap,
    mapImageSrcSet: `${mangroveMap480} 480w, ${mangroveMap768} 768w, ${mangroveMap} 1463w`,
    mapImageSizes: '(max-width: 767px) calc(100vw - 48px), (min-width: 768px) and (max-width: 1023px) calc(100vw - 148px), 660px',
    mapSource: 'WIF foundation',
    statistics: {
      carbonSequestered: '44,345',
      bufferPool: '32,882',
      creditsIssued: '211,636',
      creditsRetired: '167,291',
      source: 'VCS',
      permanenceRisk: { percentage: 21, label: 'Risk to permanency' }
    },
    benefits: [
      {
        number: 1,
        title: 'Carbon Sequestration',
        description: 'Mangroves are highly effective at sequestering carbon due to the dense biomass and rich soil carbon storage capacity of mangrove ecosystems. This makes them valuable for climate change mitigation.'
      },
      {
        number: 2,
        title: 'Low permanence risk',
        description: 'The project has a low permanence risk and adequate buffer pool of 21%. The project uses 30-year land use agreements to ensure sustained restoration, reducing the risk of reversal.'
      },
      {
        number: 3,
        title: 'Low additionality risk',
        description: 'The project used conservative assumptions in its baseline scenario. The project is implemented by WWF, a non-profit organization, with no financial return other than carbon credits. The mangroves were degraded and not being restored prior to the project.'
      },
      {
        number: 4,
        title: 'Community and biodiversity',
        description: 'The project has engaged over 11,000 people across 16 villages and provides significant socio-economic benefits. The restoration of mangrove ecosystems supports the recovery of biodiversity, including fish, birds, and other wildlife. Mangroves filter pollutants and improve water quality.'
      }
    ],
    keywords: [
      'mangrove', 'myanmar', 'blue carbon', 'coastal', 'marine', 'wetland', 'wetlands',
      'restoration', 'reforestation', 'afforestation', 'conservation', 'biodiversity',
      'community', 'livelihood', 'AR-AMS004', 'AMS', 'small-scale', 'ayeyarwady',
      'methodology', 'protocol', 'standard', 'validation', 'verification', 'high quality',
      'VCM', 'voluntary carbon market'
    ]
  },
  {
    id: 'humbo-ethiopia',
    title: 'Humbo Ethiopia Assisted Natural Regeneration Project',
    organization: 'World Vision Australia',
    organizationId: 'GS10220',
    registry: 'Gold Standard',
    registryUrl: 'https://registry.goldstandard.org/projects/details/1922',
    tags: ['REFORESTATION', 'CARBON CREDITS'],
    lensLabel: 'Co-benefits & community ownership',
    mainImage: humboMain,
    mainImageSrcSet: `${humboMain640} 640w, ${humboMain960} 960w, ${humboMain} 1400w`,
    strengths: [
      { text: 'Verified carbon removal through assisted natural regeneration of 2,724 hectares' },
      { text: 'Strong community ownership via seven cooperative societies with legal land title' },
      { text: 'Farmer Managed Natural Regeneration (FMNR), low-cost, proven restoration technique' }
    ],
    sdgs: [
      { number: 1, title: 'No Poverty', bgColor: '#E5243B', minWidth: 55 },
      { number: 5, title: 'Gender Equality', bgColor: '#FF3A21', minWidth: 55 },
      { number: 8, title: 'Decent Work and Economic Growth', bgColor: '#A21942', minWidth: 60 },
      { number: 13, title: 'Climate Action', bgColor: '#3F7E44', minWidth: 55 },
      { number: 15, title: 'Life on Land', bgColor: '#56C02B', minWidth: 55 }
    ],
    rating: 'AA',
    ratingAgency: 'BeZero',
    ratingNote: 'AA - Very high likelihood of achieving 1 tonne of CO₂e avoided or removed',
    projectType: 'Afforestation / Reforestation / Assisted Natural Regeneration',
    location: 'Southwestern Ethiopia, mountainous region',
    duration: '2006 to 2021',
    reductionRemoval: 'Removal',
    methodology: 'AR-AM0003: Afforestation and reforestation of degraded land through tree planting, assisted natural regeneration and control of animal grazing',
    about: 'The reforestation activity involves the restoration of indigenous tree species in a mountainous region of South Western Ethiopia. The project zone covers approximately 2,724 hectares across 5 strata. It contributes to climate change mitigation by creating GHG sinks through assisted natural regeneration of degraded lands, using Farmer Managed Natural Regeneration (FMNR) techniques managed by seven community cooperative societies.',
    summary: '2,724 ha of indigenous forest restored via Farmer Managed Natural Regeneration. Seven community cooperatives with legal land ownership, creating 195 jobs.',
    galleryImages: [humboArea, humboSign],
    projectImages: [humboMap, humboProjectBoundary],
    statistics: {
      carbonSequestered: '13,572',
      bufferPool: '29,343',
      creditsIssued: '240,371',
      creditsRetired: '226,799',
      source: 'Gold Standard',
      permanenceRisk: { percentage: 15, label: 'Risk to permanency' }
    },
    benefits: [
      {
        number: 1,
        title: 'Carbon Sequestration',
        description: 'Sequesters approximately 29,343 tonnes of CO₂e annually through restoration of indigenous tree species across 2,724 hectares of degraded land using Farmer Managed Natural Regeneration.'
      },
      {
        number: 2,
        title: 'Community Ownership & FMNR',
        description: 'Seven community cooperative societies hold legal ownership of 2,724 hectares, managing the land using FMNR techniques. The project has created 195 jobs, providing stable income for local households through cooperative-based enterprise.'
      },
      {
        number: 3,
        title: 'Biodiversity & Endemic Species',
        description: 'Restoration uses endemic species including Acacia spp., Podocarpus facutus, Olea africana, and Cordia africana. The area now hosts 87 tree species, creating diverse habitats for vulnerable and endangered species on the IUCN Red List.'
      },
      {
        number: 4,
        title: 'SDG Co-benefits',
        description: 'Certified impacts across five SDGs: No Poverty (195 jobs, income diversification), Gender Equality (women\'s economic empowerment), Decent Work (cooperative enterprise), Climate Action (29,343 tCO₂e/year), and Life on Land (restoration of threatened Ethiopian Montane woodlands).'
      }
    ],
    keywords: [
      'humbo', 'ethiopia', 'assisted natural regeneration', 'ANR', 'FMNR',
      'farmer managed', 'reforestation', 'afforestation', 'forest', 'forestry',
      'woodland', 'community', 'cooperative', 'community cooperative',
      'indigenous', 'mountain', 'world vision',
      'AR-AM0003', 'AM0003', 'CDM', 'gold standard', 'high quality',
      'methodology', 'protocol', 'standard', 'validation', 'verification',
      'carbon', 'credit', 'credits', 'VCM', 'voluntary carbon market'
    ]
  }
];

export function getCaseStudyById(id: string): CaseStudyData | undefined {
  return caseStudies.find(cs => cs.id === id);
}
