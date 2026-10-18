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

// Humbo field photo (Nina R, CC BY 2.0 via Wikimedia Commons)
import humboFieldPhoto from '@/assets/case-studies/humbo/entoto-nina-r.webp';
import humboFieldPhoto640 from '@/assets/case-studies/humbo/entoto-nina-r-640.webp';

// Humbo satellite images
import humboBefore from '@/assets/case-studies/humbo/satellite/humbo-ethiopia-older-2017-12-30.webp';
import humboAfter from '@/assets/case-studies/humbo/satellite/humbo-ethiopia-recent-2026-06-06.webp';
import humboBoundaryAfter from '@/assets/case-studies/humbo/satellite/humbo-ethiopia-recent-2026-06-06-boundary.webp';

// EthioTrees field photos (Jan Nyssen, CC BY-SA 4.0 via Wikimedia Commons)
import ethiotreesFieldPhoto from '@/assets/case-studies/ethiotrees/ethiotrees-exclosure-hero.webp';
import ethiotreesFieldPhoto640 from '@/assets/case-studies/ethiotrees/ethiotrees-exclosure-hero-640.webp';
import ethiotreesGalleryChurch from '@/assets/case-studies/ethiotrees/ethiotrees-gallery-church-forest.webp';
import ethiotreesGalleryZibanDake from '@/assets/case-studies/ethiotrees/ethiotrees-gallery-ziban-dake.webp';

// EthioTrees satellite images
import ethiotreesOverviewAfter from '@/assets/case-studies/ethiotrees/satellite/ethiotrees-overview-recent-2026-01-07-boundary.webp';
import ethiotreesMayGenetBefore from '@/assets/case-studies/ethiotrees/satellite/ethiotrees-may-genet-older-2016-11-03.webp';
import ethiotreesMayGenetAfter from '@/assets/case-studies/ethiotrees/satellite/ethiotrees-may-genet-recent-2025-11-18.webp';
import ethiotreesMayHuwoBefore from '@/assets/case-studies/ethiotrees/satellite/ethiotrees-may-huwo-older-2016-11-03.webp';
import ethiotreesMayHuwoAfter from '@/assets/case-studies/ethiotrees/satellite/ethiotrees-may-huwo-recent-2025-11-18.webp';
import ethiotreesAfedenaBefore from '@/assets/case-studies/ethiotrees/satellite/ethiotrees-afedena-older-2016-11-03.webp';
import ethiotreesAfedenaAfter from '@/assets/case-studies/ethiotrees/satellite/ethiotrees-afedena-recent-2025-11-18.webp';

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
    duration: '2015 to 2035',
    reductionRemoval: 'Both',
    methodology: 'AR-AM0014',
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
        attribution: 'Captured with Copernicus Sentinel-2.',
      },
      {
        before: thabawkanBefore,
        after: thabawkanAfter,
        beforeLabel: 'Jan 2017',
        afterLabel: 'Dec 2025',
        caption: 'Thabawkan village tract: 2018–2019 planting areas.',
        attribution: 'Captured with Copernicus Sentinel-2.',
      },
      {
        before: thaegoneBefore,
        after: thaegoneAfter,
        beforeLabel: 'Jan 2017',
        afterLabel: 'Dec 2025',
        caption: 'Thaegone village tract: 2018–2019 planting areas.',
        attribution: 'Captured with Copernicus Sentinel-2.',
      },
    ],
    statistics: {
      carbonSequestered: '63,815',
      bufferPool: '48,937',
      creditsIssued: '290,025',
      creditsRetired: '226,210',
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
        description: 'The project used conservative assumptions in its baseline scenario. The project is implemented by Worldview International Foundation, a non-profit organization, with no financial return other than carbon credits. The mangroves were degraded and not being restored prior to the project.'
      },
      {
        number: 4,
        title: 'Community and biodiversity',
        description: 'The project has engaged over 11,000 people across 16 villages and provides significant socio-economic benefits. The restoration of mangrove ecosystems supports the recovery of biodiversity, including fish, birds, and other wildlife. Mangroves filter pollutants and improve water quality.'
      }
    ],
    keywords: [
      'mangrove', 'myanmar', 'blue carbon', 'coastal', 'marine', 'wetland', 'wetlands',
      'restoration', 'reforestation', 'afforestation', 'conservation', 'protection', 'biodiversity',
      'community', 'livelihood', 'AR-AM0014', 'AM0014', 'ayeyarwady',
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
    mainImageSrcSet: `${humboFieldPhoto640} 640w, ${humboFieldPhoto} 1600w`,
    mainImageCaption: 'Illustrative photo: forested hillsides in the Entoto mountains, Ethiopia. Photo by Nina R, CC BY 2.0, via Wikimedia Commons.',
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
    duration: '2006 to 2036',
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
        attribution: 'Captured with Copernicus Sentinel-2.',
      },
    ],
    statistics: {
      carbonSequestered: '12,887',
      creditsIssued: '240,371',
      creditsRetired: '227,484',
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
  },
  {
    id: 'ethiotrees-tigray',
    title: 'EthioTrees: Ecosystem Restoration and Agroforestry by Landless and Smallholder Farmers in Tigray (North Ethiopia)',
    organization: 'EthioTrees / Climate Lab',
    organizationId: 'PV201719',
    registry: 'Plan Vivo',
    registryUrl: 'https://www.planvivo.org/projects/ethiotrees-ethiopia',
    tags: ['REFORESTATION', 'AGROFORESTRY'],
    lensLabel: 'Community benefit sharing',
    mainImage: ethiotreesFieldPhoto,
    mainImageSrcSet: `${ethiotreesFieldPhoto640} 640w, ${ethiotreesFieldPhoto} 1600w`,
    mainImageCaption: 'Wooded exclosure hillside at May Be\'ati in the Tembien Highlands. Photo by Jan Nyssen, CC BY-SA 4.0, via Wikimedia Commons.',
    strengths: [
      { text: 'Community-governed exclosures run by associations of landless farmers' },
      { text: '60% of carbon income paid to participants and community funds' },
      { text: 'Conservative carbon accounting based on field re-measurement' },
      { text: 'Direct income from frankincense, honey, and cut-and-carry fodder' }
    ],
    sdgs: [
      { number: 1, title: 'No Poverty' },
      { number: 2, title: 'Zero Hunger' },
      { number: 6, title: 'Clean Water and Sanitation' },
      { number: 8, title: 'Decent Work and Economic Growth' },
      { number: 13, title: 'Climate Action' },
      { number: 15, title: 'Life on Land' }
    ],
    rating: 'BBB',
    ratingAgency: 'BeZero',
    ratingNote: 'BBB - Moderate likelihood of achieving 1 tonne of CO₂e avoided or removed. Rated A by Sylvera.',
    projectType: 'Ecosystem restoration / Agroforestry',
    location: 'Tembien Highlands, Tigray Region, Ethiopia',
    duration: '2016 to 2066',
    reductionRemoval: 'Removal',
    methodology: 'Plan Vivo Carbon Standard (PV Climate v4)',
    about: 'Communities restore degraded land in the Tembien Highlands by closing it to grazing, so woodland and soil carbon recover; smallholders also plant trees on their farms. The project grew from 541 ha in 2016 to 30,031 ha across 145 community groups by 2026. Its main permanence risk is post-war instability in Tigray, which verifiers rated low.',
    summary: '30,031 ha of community-managed exclosures restored in the Tigray highlands. 60% of carbon income reaches participants and funds water, schools, and food aid.',
    overviewMap: {
      image: ethiotreesOverviewAfter,
      caption: 'EthioTrees project areas (white) across Dogua and Kola Tembien, Jan 2026. Outlines are traced from the project map in the PDD (Annex 8) and are approximate.',
      attribution: 'Captured with Copernicus Sentinel-2.'
    },
    beforeAfterImages: [
      {
        before: ethiotreesMayGenetBefore,
        after: ethiotreesMayGenetAfter,
        beforeLabel: 'Nov 2016',
        afterLabel: 'Nov 2025',
        caption: 'May Genet exclosure, added to the project in January 2017.',
        attribution: 'Captured with Copernicus Sentinel-2.',
      },
      {
        before: ethiotreesMayHuwoBefore,
        after: ethiotreesMayHuwoAfter,
        beforeLabel: 'Nov 2016',
        afterLabel: 'Nov 2025',
        caption: 'May Huwo exclosure on the escarpment, added to the project in January 2017.',
        attribution: 'Captured with Copernicus Sentinel-2.',
      },
      {
        before: ethiotreesAfedenaBefore,
        after: ethiotreesAfedenaAfter,
        beforeLabel: 'Nov 2016',
        afterLabel: 'Nov 2025',
        caption: 'Afedena exclosure, added to the project in January 2017.',
        attribution: 'Captured with Copernicus Sentinel-2.',
      },
    ],
    galleryImages: [
      ethiotreesGalleryChurch,
      ethiotreesGalleryZibanDake,
    ],
    galleryCaption: 'Field photos by Jan Nyssen, CC BY-SA 4.0, via Wikimedia Commons.',
    statistics: {
      carbonSequestered: '512,136',
      bufferPool: '85,751',
      creditsIssued: '760,872',
      creditsRetired: '248,736',
      source: 'Plan Vivo',
      permanenceRisk: { percentage: 10, label: 'Risk to permanency' }
    },
    benefits: [
      {
        number: 1,
        title: 'Direct benefit sharing',
        description: 'Sixty percent of carbon income goes to participants and community funds. The project has paid $3.76 million to participants and holds $302,366 in trust. Community assemblies decide the spending: water reservoirs, classrooms, solar systems, and food aid.'
      },
      {
        number: 2,
        title: 'Conservative, verified carbon',
        description: 'Field crews measure biomass and soil carbon in fixed plots and transects. The 2023 re-sampling gave a sequestration rate of 8.2 tCO₂e per hectare per year, below the original estimate of 9.2. The MUTU verification reported no outstanding corrective actions.'
      },
      {
        number: 3,
        title: 'Income for landless farmers',
        description: 'Associations of landless farmers manage the exclosures and earn income from frankincense, honey, and cut-and-carry fodder. The market price of frankincense resin has doubled since 2016. Another 1,567 smallholder households run agroforestry plots.'
      },
      {
        number: 4,
        title: 'Water and food security',
        description: 'Soil and water conservation raised groundwater levels and revived springs. In Meam Atali, farmers now irrigate all year. The project built over 10 large reservoirs and gave food aid to 29,135 people during the 2021 famine.'
      }
    ],
    keywords: [
      'ethiotrees', 'tigray', 'ethiopia', 'exclosure', 'hizaeti', 'agroforestry',
      'frankincense', 'boswellia', 'plan vivo', 'pv climate', 'pvc',
      'landless farmers', 'tembien', 'benefit sharing', 'payments for ecosystem services',
      'pes', 'restoration', 'community', 'afforestation', 'reforestation',
      'methodology', 'standard', 'validation', 'verification', 'high quality',
      'carbon', 'credit', 'credits', 'VCM', 'voluntary carbon market'
    ]
  }
];

export function getCaseStudyById(id: string): CaseStudyData | undefined {
  return caseStudies.find(cs => cs.id === id);
}
