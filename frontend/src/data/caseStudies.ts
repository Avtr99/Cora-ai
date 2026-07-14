import type { CaseStudyData } from './caseStudyTypes';

// Mangrove field photo (CC0 / public domain)
import mangroveFieldPhoto from '@/assets/case-studies/mangrove/Mangrove_Rakhine_Myanmar_2_landscape.webp';
import mangroveFieldPhoto640 from '@/assets/case-studies/mangrove/Mangrove_Rakhine_Myanmar_2_landscape-640.webp';

// Mangrove satellite images
import mangroveOverviewBoundaryAfter from '@/assets/case-studies/mangrove/satellite/myanmar-mangrove-overview-recent-2025-12-05-boundary.webp';
import magyiBefore from '@/assets/case-studies/mangrove/satellite/magyi-older-2017-12-17.webp';
import magyiAfter from '@/assets/case-studies/mangrove/satellite/magyi-recent-2025-12-15.webp';
import thabawkanBefore from '@/assets/case-studies/mangrove/satellite/thabawkan-older-2017-01-26.webp';
import thabawkanAfter from '@/assets/case-studies/mangrove/satellite/thabawkan-recent-2025-12-05.webp';
import thaegoneBefore from '@/assets/case-studies/mangrove/satellite/thaegone-older-2017-01-26.webp';
import thaegoneAfter from '@/assets/case-studies/mangrove/satellite/thaegone-recent-2025-12-05.webp';

// Humbo field photo (Pexels License, Abiy Fikru)
import humboFieldPhoto from '@/assets/case-studies/humbo/pexels-abiy-fikru-176179-27534668.webp';
import humboFieldPhoto640 from '@/assets/case-studies/humbo/pexels-abiy-fikru-176179-27534668-640.webp';

// Humbo satellite images
import humboBefore from '@/assets/case-studies/humbo/satellite/humbo-ethiopia-older-2017-12-30.webp';
import humboAfter from '@/assets/case-studies/humbo/satellite/humbo-ethiopia-recent-2026-06-06.webp';
import humboBoundaryAfter from '@/assets/case-studies/humbo/satellite/humbo-ethiopia-recent-2026-06-06-boundary.webp';

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
    mainImage: mangroveFieldPhoto,
    mainImageSrcSet: `${mangroveFieldPhoto640} 640w, ${mangroveFieldPhoto} 960w`,
    mainImageCaption: 'Photo by scottedmunds / iNaturalist. CC0 / public domain.',
    strengths: [
      { text: 'Strong biodiversity' },
      { text: 'Verified carbon sink' },
      { text: 'Robust measures against non-permanence risks' },
      { text: 'Run by skilled, local experts, with development and livelihood in biodiversity' }
    ],
    sdgs: [
      { number: 8, title: 'Decent Work and Economic Growth' },
      { number: 13, title: 'Climate Action' },
      { number: 14, title: 'Life Below Water' }
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
    overviewMap: {
      image: mangroveOverviewBoundaryAfter,
      caption: 'Project area overview: the restored mangrove boundary (white) is visible across all three village tracts.',
      attribution: 'Captured with Copernicus Sentinel-2.'
    },
    beforeAfterImages: [
      {
        before: magyiBefore,
        after: magyiAfter,
        beforeLabel: 'Dec 2017',
        afterLabel: 'Dec 2025',
        caption: 'Magyi village tract: mangrove restoration since 2015.',
      },
      {
        before: thabawkanBefore,
        after: thabawkanAfter,
        beforeLabel: 'Jan 2017',
        afterLabel: 'Dec 2025',
        caption: 'Thabawkan village tract: 2018–2019 planting areas.',
      },
      {
        before: thaegoneBefore,
        after: thaegoneAfter,
        beforeLabel: 'Jan 2017',
        afterLabel: 'Dec 2025',
        caption: 'Thaegone village tract: 2018–2019 planting areas.',
      },
    ],
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
    mainImage: humboFieldPhoto,
    mainImageSrcSet: `${humboFieldPhoto640} 640w, ${humboFieldPhoto} 1280w`,
    mainImageCaption: 'Photo by Abiy Fikru on Pexels.',
    strengths: [
      { text: 'Verified carbon removal through assisted natural regeneration of 2,724 hectares' },
      { text: 'Strong community ownership via seven cooperative societies with legal land title' },
      { text: 'Farmer Managed Natural Regeneration (FMNR), low-cost, proven restoration technique' }
    ],
    sdgs: [
      { number: 1, title: 'No Poverty' },
      { number: 5, title: 'Gender Equality' },
      { number: 8, title: 'Decent Work and Economic Growth' },
      { number: 13, title: 'Climate Action' },
      { number: 15, title: 'Life on Land' }
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
    overviewMap: {
      image: humboBoundaryAfter,
      caption: 'Humbo project area, Jun 2026. Boundary is approximate, based on the monitoring-report GPS coordinates.',
      attribution: 'Captured with Copernicus Sentinel-2.'
    },
    beforeAfterImages: [
      {
        before: humboBefore,
        after: humboAfter,
        beforeLabel: 'Dec 2017',
        afterLabel: 'Jun 2026',
        caption: 'Humbo project area: before (2017) and after (2026) assisted natural regeneration.',
      },
    ],
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
