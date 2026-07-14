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

> Humbo project area, Jun 2026. Boundary is approximate, based on the monitoring-report GPS coordinates. Contains modified Copernicus Sentinel data 2026, processed by Cora AI.

The shared satellite attribution line is:

> Contains modified Copernicus Sentinel data <year>, processed by Cora AI.
>
> Replace `<year>` with the year of the Sentinel-2 scene (e.g. 2026).

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

## Field photographs

### Mangrove case-study hero image

| Filename | Description | Credit |
|---|---|---|
| [`case-studies/mangrove/Mangrove_Rakhine_Myanmar_2_landscape.webp`](https://github.com/Avtr99/Cora-ai/blob/main/frontend/src/assets/case-studies/mangrove/Mangrove_Rakhine_Myanmar_2_landscape.webp) | Mangrove forest illustrative photo. | Photo by [scottedmunds](https://www.inaturalist.org/observations/146600482) / iNaturalist, via [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Mangrove,_Rakhine,_Myanmar_2.jpg). License: [CC0 1.0 Universal / Public Domain](https://creativecommons.org/publicdomain/zero/1.0/). |

Required credit line on the page:
> Photo by scottedmunds / iNaturalist, via Wikimedia Commons. CC0 / public domain.

### Humbo Ethiopia case-study hero image

| Filename | Description | Credit |
|---|---|---|
| [`case-studies/humbo/pexels-abiy-fikru-176179-27534668.webp`](https://github.com/Avtr99/Cora-ai/blob/main/frontend/src/assets/case-studies/humbo/pexels-abiy-fikru-176179-27534668.webp) | Mountain forest landscape photo. | Photo by [Abiy Fikru](https://www.pexels.com/photo/27534668/) on Pexels. [Pexels License](https://www.pexels.com/license/): free for commercial and non-commercial use, no attribution required. |

Credit line on the page:
> Photo by Abiy Fikru on Pexels.

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
- **Citation:** Pamela Quartson, Barbara K Haya, Tyler Bernard, Aline Abayo, Xinyun Rong, Ivy S So, Micah Elias. (2026). *Voluntary Registry Offsets Database v2026-04*, Berkeley Carbon Trading Project, University of California, Berkeley.
- **Processing:** [`frontend/scripts/convert-projects.mjs`](https://github.com/Avtr99/Cora-ai/blob/main/frontend/scripts/convert-projects.mjs) converts the CSV into [`frontend/public/data/projects-summary.json`](https://github.com/Avtr99/Cora-ai/blob/main/frontend/public/data/projects-summary.json) and [`frontend/public/data/projects-detail.json`](https://github.com/Avtr99/Cora-ai/blob/main/frontend/public/data/projects-detail.json).
- **Display:** [`frontend/src/components/projects/ProjectAttribution.tsx`](https://github.com/Avtr99/Cora-ai/blob/main/frontend/src/components/projects/ProjectAttribution.tsx)
