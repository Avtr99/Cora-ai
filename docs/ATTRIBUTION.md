# Satellite image candidates

These images are true-color composites generated from public **Sentinel-2** data
(European Union's Copernicus programme). They are used on the case-study pages as
before/after proof of restoration impact.

## Source

- Data: Sentinel-2 Level-2A (surface reflectance)
- Provider: [Earth Search by Element84](https://earth-search.aws.element84.com/v1/)
- License: Copernicus open data, free to use with attribution.

## Required attribution

The case-study pages display the caption and attribution together as one line, e.g.:

> Humbo project area, Jun 2026. Boundary is approximate, based on the monitoring-report GPS coordinates. Captured with Copernicus Sentinel-2.

The shared satellite attribution line is simplified to:

> Captured with Copernicus Sentinel-2.

## Generated files

### Myanmar Mangrove Restoration (VCS-1764)

| Location | Date | Description |
|---|---|---|
| `case-studies/mangrove/satellite/myanmar-mangrove-overview-recent-2025-12-05-boundary.webp` | 2025-12-05 | Project-wide overview mosaic showing all three village tracts and the official KML boundary. |
| `case-studies/mangrove/satellite/magyi-recent-2025-12-15.webp` | 2025-12-15 | Magyi village tract after restoration (2015–2017 planting). |
| `case-studies/mangrove/satellite/magyi-older-2017-12-17.webp` | 2017-12-17 | Magyi village tract before restoration. |
| `case-studies/mangrove/satellite/thabawkan-recent-2025-12-05.webp` | 2025-12-05 | Thabawkan village tract after restoration (2018–2019 planting). |
| `case-studies/mangrove/satellite/thabawkan-older-2017-01-26.webp` | 2017-01-26 | Thabawkan village tract before restoration. |
| `case-studies/mangrove/satellite/thaegone-recent-2025-12-05.webp` | 2025-12-05 | Thaegone village tract after restoration (2018–2019 planting). |
| `case-studies/mangrove/satellite/thaegone-older-2017-01-26.webp` | 2017-01-26 | Thaegone village tract before restoration. |

### Humbo Ethiopia Assisted Natural Regeneration (GS10220)

| Location | Date | Description |
|---|---|---|
| `case-studies/humbo/satellite/humbo-ethiopia-recent-2026-06-06-boundary.webp` | 2026-06-06 | Project-wide overview with an approximate boundary overlay. |
| `case-studies/humbo/satellite/humbo-ethiopia-recent-2026-06-06.webp` | 2026-06-06 | Recent Sentinel-2 true-color view used in the before/after slider. |
| `case-studies/humbo/satellite/humbo-ethiopia-older-2017-12-30.webp` | 2017-12-30 | Early Sentinel-2 true-color view used in the before/after slider. |

The Humbo boundary overlay is **approximate**, based on the GPS coordinate box
stated in the project monitoring report (lat 6°41'04.28"N to 6°46'48.47"N,
lon 37°48'35.44"E to 37°55'14.51"E). The actual strata-corner coordinates were
not available in the materials found so far.

### EthioTrees Tigray (PV_2017_19)

| Location | Date | Description |
|---|---|---|
| `case-studies/ethiotrees/satellite/ethiotrees-overview-recent-2026-01-07-boundary.webp` | 2026-01-07 | Same-day mosaic of 7 Earth Search L2A TCI granules (tiles 37PDQ/37PDR/37PEQ/37PER, S2A + S2B, 0% cloud). Frame 38.607–39.761°E, 13.199–14.046°N, all 59 PDD project areas outlined in white. |
| `case-studies/ethiotrees/satellite/ethiotrees-may-genet-older-2016-11-03.webp` | 2016-11-03 | Planetary Computer L2A `S2A_MSIL2A_20161103T075102_R135_T37PER`. May Genet exclosure (map p.18), outlined. |
| `case-studies/ethiotrees/satellite/ethiotrees-may-genet-recent-2025-11-18.webp` | 2025-11-18 | Planetary Computer L2A `S2A_MSIL2A_20251118T080451_R135_T37PER`. Same frame. |
| `case-studies/ethiotrees/satellite/ethiotrees-may-huwo-older-2016-11-03.webp` | 2016-11-03 | As above. May Huwo exclosure (map p.20), outlined. |
| `case-studies/ethiotrees/satellite/ethiotrees-may-huwo-recent-2025-11-18.webp` | 2025-11-18 | As above. Same frame. |
| `case-studies/ethiotrees/satellite/ethiotrees-afedena-older-2016-11-03.webp` | 2016-11-03 | As above. Afedena exclosure (map p.22), outlined. |
| `case-studies/ethiotrees/satellite/ethiotrees-afedena-recent-2025-11-18.webp` | 2025-11-18 | As above. Same frame. |

**Boundary sources**

- *Overview*: the 59 green project areas on the PDD v4 project map (Annex 8,
  p.105), georeferenced with its graticule lines (plate carrée, fit residual
  < 0.2 px). Total traced area 11,376 ha vs. 11,176 ha stated in the PDD.
  Map resolution is ~125 m per pixel, so outlines are approximate.
- *Sliders*: the dashed "Exclosure boundary" line on the per-site maps in the
  2016–17 annual report (`EthioTrees_2016_Annual_Report.pdf`, p.18/20/22),
  georeferenced with each map's graticule ticks (Web Mercator). Traced areas
  match the report: May Genet 50.2 ha (51), May Huwo 51.1 ha (53), Afedena
  81.3 ha (81).

All outlines use the mangrove overview style: thin white line, no fill, no labels.

**Slider processing**

Both dates are post-rainy season (November), same orbit (R135), same tile.
Nov 2016 is before these three sites joined the project (January 2017). Both
dates are converted to surface reflectance (the -0.1 offset applied to the
2025 scene, baseline 05.11) and share one linear stretch: reflectance 0 to
0.258 (99.5th percentile pooled over all bands of all six images) mapped to
0–255, gamma 1.2, with the same range for R, G and B. Colour differences
between the dates are therefore real.
February–March (dry season) imagery was not used: grass is dormant then and
the exclosures barely differ from their surroundings.

No vector/GIS boundaries are published for this project (Plan Vivo, Climate
Lab and the PDD do not provide KML or shapefiles).

## Field photographs

### Mangrove case-study hero image

| Filename | Description | Credit |
|---|---|---|
| [`case-studies/mangrove/Mangrove_Rakhine_Myanmar_2_landscape.webp`](https://github.com/Avtr99/Cora-ai/blob/main/frontend/src/assets/case-studies/mangrove/Mangrove_Rakhine_Myanmar_2_landscape.webp) | Mangrove forest illustrative photo. | Photo by [scottedmunds](https://www.inaturalist.org/observations/146600482) / iNaturalist, via [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Mangrove,_Rakhine,_Myanmar_2.jpg). License: [CC0 1.0 Universal / Public Domain](https://creativecommons.org/publicdomain/zero/1.0/). |

Required credit line on the page:
> Photo by scottedmunds / iNaturalist. CC0 / public domain.

### Humbo Ethiopia case-study hero image

| Filename | Description | Credit |
|---|---|---|
| [`case-studies/humbo/entoto-nina-r.webp`](https://github.com/Avtr99/Cora-ai/blob/main/frontend/src/assets/case-studies/humbo/entoto-nina-r.webp) (+ `-640` variant) | Forested hillsides in the Entoto mountains, Ethiopia (illustrative landscape, not the project site). | Photo by [Nina R](https://www.flickr.com/photos/150102727@N06/50813987716/), via [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Ethiopia_(50813987716).jpg). License: [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/). The webp conversions are resized derivatives. |

Credit line on the page:
> Illustrative photo: forested hillsides in the Entoto mountains, Ethiopia. Photo by Nina R, CC BY 2.0, via Wikimedia Commons.

### EthioTrees case-study hero and gallery images

All photos are from **Wikimedia Commons** and show the actual project area
(Dogu'a Tembien, Tigray). All are licensed **CC BY-SA 4.0** (verified against
the Commons file pages). CC BY-SA requires attribution (shown in the page
captions) and share-alike on adaptations. The webp conversions are resized
derivatives and carry the same license.

| Filename | Description | Source file | Credit / License |
|---|---|---|---|
| `case-studies/ethiotrees/ethiotrees-exclosure-hero.webp` (+ `-640` variant) | Wooded exclosure hillside at May Be'ati, Dogu'a Tembien. | [May Be'ati.jpg](https://commons.wikimedia.org/wiki/File:May_Be%27ati.jpg) | Jan Nyssen, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `case-studies/ethiotrees/ethiotrees-gallery-church-forest.webp` | Inda Abba Hadera church forest in a gorge. | [Inda Abba Hadera forest.jpg](https://commons.wikimedia.org/wiki/File:Inda_Abba_Hadera_forest.jpg) | Jan Nyssen, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| `case-studies/ethiotrees/ethiotrees-gallery-ziban-dake.webp` | Field visit on a degraded Boswellia slope at Ziban Dake. | [Ziban Dake 2.jpg](https://commons.wikimedia.org/wiki/File:Ziban_Dake_2.jpg) | Jan Nyssen, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |

Credit line on the page (hero):
> Photo by Jan Nyssen, CC BY-SA 4.0, via Wikimedia Commons.

Note: an earlier draft used photographs extracted from the EthioTrees PDD and
Annual Report PDFs. Those images are EthioTrees copyright with no public reuse
license, so they were removed in favour of the Commons set above.

## Notes

- These are real satellite images of the actual project locations, not field photographs.
- The Myanmar overview is a two-tile Sentinel-2 mosaic (tiles 46QFD and 46QFE)
  because the project area straddles the tile boundary.
- The KML boundary for Myanmar is the official project boundary file from the registry.

## Data sources

### Voluntary Carbon Market project database

The project comparison feature uses the *Voluntary Registry Offsets Database* from the
Berkeley Carbon Trading Project, Goldman School of Public Policy, University of California,
Berkeley.

- **Source:** https://gspp.berkeley.edu/berkeley-carbon-trading-project/offsets-database
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Citation:** Pamela Quartson, Barbara K Haya, Tyler Bernard, Aline Abayo, Xinyun Rong, Ivy S So, Micah Elias. (2026). *Voluntary Registry Offsets Database v2026-06*, Berkeley Carbon Trading Project, University of California, Berkeley.
- **Processing:** [`frontend/scripts/convert-projects.mjs`](https://github.com/Avtr99/Cora-ai/blob/main/frontend/scripts/convert-projects.mjs) converts the CSV into [`frontend/public/data/projects-summary.json`](https://github.com/Avtr99/Cora-ai/blob/main/frontend/public/data/projects-summary.json) and [`frontend/public/data/projects-detail.json`](https://github.com/Avtr99/Cora-ai/blob/main/frontend/public/data/projects-detail.json).
- **Display:** [`frontend/src/components/projects/ProjectAttribution.tsx`](https://github.com/Avtr99/Cora-ai/blob/main/frontend/src/components/projects/ProjectAttribution.tsx)
