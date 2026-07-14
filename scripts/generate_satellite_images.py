#!/usr/bin/env python3
"""
Generate project-specific satellite images from public Sentinel-2 data.

Outputs are written to frontend/src/assets/case-studies/satellite-candidates/
so they can be reviewed before replacing the existing case-study images.

Sentinel-2 imagery: Copernicus programme, free to use with attribution.
Attribution: "Contains modified Copernicus Sentinel data <year>, processed by Cora AI."
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import rasterio
import requests
from PIL import Image
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.vrt import WarpedVRT
from rasterio.windows import from_bounds
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

STAC_URL = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-l2a"

# Output directory, kept separate from the current case-study assets.
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "frontend" / "src" / "assets" / "case-studies" / "satellite-candidates"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SITES: dict[str, dict] = {
    "myanmar-mangrove-overview": {
        "label": "Myanmar Mangrove Restoration (VCS-1764) - Overview",
        # Full KML project extent; needs a two-tile mosaic because the AOI straddles
        # Sentinel-2 tiles 46QFD (south) and 46QFE (north).
        "bbox": [94.44, 17.03, 94.55, 17.20],
        "mosaic": True,
        "recent_range": ("2025-11-01", "2026-03-31"),
        "older_range": ("2017-01-01", "2017-12-31"),
    },
    "magyi": {
        "label": "Magyi Village Tract (VCS-1764)",
        # 0.01 degree margin around the KML polygons so boundary lines are not clipped.
        "bbox": [94.443, 17.029, 94.521, 17.099],
        "recent_range": ("2025-11-01", "2026-03-31"),
        "older_range": ("2017-01-01", "2017-12-31"),
    },
    "thabawkan": {
        "label": "Thabawkan Village Tract (VCS-1764)",
        "bbox": [94.477, 17.099, 94.546, 17.188],
        "recent_range": ("2025-11-01", "2026-03-31"),
        "older_range": ("2017-01-01", "2017-12-31"),
    },
    "thaegone": {
        "label": "Thaegone Village Tract (VCS-1764)",
        "bbox": [94.437, 17.111, 94.508, 17.198],
        "recent_range": ("2025-11-01", "2026-03-31"),
        "older_range": ("2017-01-01", "2017-12-31"),
    },
    "humbo-ethiopia": {
        "label": "Humbo Ethiopia Assisted Natural Regeneration (GS10220)",
        # Landscape bbox (13:8) around the Humbo project strata.
        "bbox": [37.784, 6.68, 37.946, 6.80],
        "recent_range": ("2026-05-01", "2026-09-30"),
        "older_range": ("2016-01-01", "2017-12-31"),
    },
}


def bbox_metrics(bbox: list[float]) -> tuple[int, int]:
    """Return target (width, height) in pixels at ~10 m Sentinel-2 resolution."""
    lon_min, lat_min, lon_max, lat_max = bbox
    lat_center = (lat_min + lat_max) / 2
    meters_per_deg_lon = 111_320 * math.cos(math.radians(lat_center))
    meters_per_deg_lat = 111_320
    width_m = (lon_max - lon_min) * meters_per_deg_lon
    height_m = (lat_max - lat_min) * meters_per_deg_lat
    width_px = max(1, int(round(width_m / 10)))
    height_px = max(1, int(round(height_m / 10)))
    return width_px, height_px


def _contains_bbox(outer: list[float], inner: list[float]) -> bool:
    """Return True if outer bbox fully contains inner bbox."""
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
)
def search_sentinel2(
    bbox: list[float],
    date_range: tuple[str, str],
    max_cloud: float = 30.0,
    require_contain: bool = True,
) -> list[dict]:
    """Query the Earth Search STAC API for Sentinel-2 L2A scenes.

    Retries on transient network errors and 5xx responses. By default returns only
    scenes whose footprint fully contains the bbox. Set require_contain=False to
    return any intersecting scene (used for mosaics).
    """
    payload = {
        "collections": [COLLECTION],
        "bbox": bbox,
        "datetime": f"{date_range[0]}T00:00:00Z/{date_range[1]}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": max_cloud}},
        "limit": 50,
    }
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(STAC_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        features = resp.json().get("features", [])
    except requests.exceptions.RequestException:
        raise
    except (ValueError, KeyError) as exc:
        print(f"  WARN: Invalid STAC API response: {exc}")
        return []
    if require_contain:
        features = [f for f in features if _contains_bbox(f["bbox"], bbox)]
    else:
        # Keep scenes that actually intersect our AOI.
        features = [
            f
            for f in features
            if not (
                f["bbox"][0] > bbox[2]
                or f["bbox"][2] < bbox[0]
                or f["bbox"][1] > bbox[3]
                or f["bbox"][3] < bbox[1]
            )
        ]
    features.sort(key=lambda f: f["properties"].get("eo:cloud_cover", 100))
    return features


def read_band(url: str, bbox: list[float], shape: tuple[int, int]) -> np.ndarray:
    """Read a single COG band, reproject it to WGS84, and clip to the bbox."""
    try:
        with rasterio.open(url) as src:
            # Reproject the source tile to WGS84 on the fly so the output is north-up and properly aligned.
            with WarpedVRT(src, crs="EPSG:4326", resampling=Resampling.bilinear) as vrt:
                window = from_bounds(bbox[0], bbox[1], bbox[2], bbox[3], vrt.transform)
                data = vrt.read(
                    1,
                    window=window,
                    out_shape=shape,
                    resampling=Resampling.bilinear,
                )
        return data.astype(np.float32)
    except rasterio.errors.RasterioError as exc:
        raise RuntimeError(f"Failed to read band from {url}: {exc}") from exc


def render_scene(feature: dict, bbox: list[float], shape: tuple[int, int]) -> tuple[np.ndarray, str, float] | None:
    """Render a true-color RGB array from a STAC feature. Returns None if coverage is poor."""
    assets = feature["assets"]
    required = ["red", "green", "blue"]
    for key in required:
        if key not in assets:
            raise KeyError(f"Missing asset {key}")

    red = read_band(assets["red"]["href"], bbox, shape)
    green = read_band(assets["green"]["href"], bbox, shape)
    blue = read_band(assets["blue"]["href"], bbox, shape)

    # Sentinel-2 L2A reflectance is stored as integer values scaled by 10000.
    scale = 1.0 / 10_000.0
    rgb = np.stack([red, green, blue], axis=-1) * scale

    # Enhance contrast: clip to a reasonable reflectance range and scale to 0-255.
    rgb = np.clip(rgb / 0.25, 0.0, 1.0)
    rgb_uint8 = (rgb * 255).astype(np.uint8)

    # Reject images with large no-data regions (source nodata is 0).
    black_fraction = np.all(rgb_uint8 == 0, axis=-1).sum() / rgb_uint8[..., 0].size
    if black_fraction > 0.05:
        return None

    date = feature["properties"]["datetime"][:10]
    cloud = feature["properties"].get("eo:cloud_cover", 0.0)
    return rgb_uint8, date, cloud


def render_mosaic(features: list[dict], bbox: list[float], shape: tuple[int, int]) -> tuple[np.ndarray, str, float] | None:
    """Render a true-color mosaic from multiple intersecting STAC features.

    Each feature should cover a different part of the AOI (e.g., adjacent
    Sentinel-2 tiles). The bands are merged with rasterio.merge.merge and then
    resampled/cropped to the requested shape.
    """
    if not features:
        return None

    required = ["red", "green", "blue"]
    for feature in features:
        assets = feature["assets"]
        for key in required:
            if key not in assets:
                raise KeyError(f"Missing asset {key}")

    width, height = shape[1], shape[0]
    xres = (bbox[2] - bbox[0]) / width
    yres = (bbox[3] - bbox[1]) / height

    def _merge_band(key: str) -> np.ndarray:
        raw_srcs: list[rasterio.DatasetReader] = []
        vrt_srcs: list[WarpedVRT] = []
        try:
            for feature in features:
                try:
                    raw_srcs.append(rasterio.open(feature["assets"][key]["href"]))
                except rasterio.errors.RasterioError as exc:
                    raise RuntimeError(
                        f"Failed to open {key} band for scene {feature.get('id', 'unknown')}: {exc}"
                    ) from exc
            # Reproject each source to WGS84 before merging so the output is in degrees
            # and all tiles share a common CRS.
            vrt_srcs = [WarpedVRT(src, crs="EPSG:4326", resampling=Resampling.bilinear) for src in raw_srcs]
            try:
                merged, _ = merge(
                    vrt_srcs,
                    bounds=(bbox[0], bbox[1], bbox[2], bbox[3]),
                    res=(xres, yres),
                    nodata=0,
                    resampling=Resampling.bilinear,
                )
            except Exception as exc:
                raise RuntimeError(f"Failed to merge {key} band: {exc}") from exc
        finally:
            for vrt in vrt_srcs:
                vrt.close()
            for src in raw_srcs:
                src.close()
        # merge returns (bands, height, width); we requested a single band.
        return merged[0]

    red = _merge_band("red")
    green = _merge_band("green")
    blue = _merge_band("blue")

    # Crop/pad to exact shape if merge returned slightly different dimensions.
    def _crop(arr: np.ndarray) -> np.ndarray:
        if arr.shape[0] > height:
            arr = arr[:height, :]
        if arr.shape[1] > width:
            arr = arr[:, :width]
        if arr.shape[0] < height or arr.shape[1] < width:
            pad_h = max(0, height - arr.shape[0])
            pad_w = max(0, width - arr.shape[1])
            arr = np.pad(arr, ((0, pad_h), (0, pad_w)), mode="constant")
        return arr

    red, green, blue = _crop(red), _crop(green), _crop(blue)

    scale = 1.0 / 10_000.0
    rgb = np.stack([red, green, blue], axis=-1) * scale
    rgb = np.clip(rgb / 0.25, 0.0, 1.0)
    rgb_uint8 = (rgb * 255).astype(np.uint8)

    black_fraction = np.all(rgb_uint8 == 0, axis=-1).sum() / rgb_uint8[..., 0].size
    if black_fraction > 0.05:
        return None

    # Use the latest date and max cloud cover among the mosaic tiles.
    dates = [f["properties"]["datetime"][:10] for f in features]
    clouds = [f["properties"].get("eo:cloud_cover", 0.0) for f in features]
    return rgb_uint8, max(dates), max(clouds)


def save_variants(rgb: np.ndarray, base_path: Path) -> None:
    """Save a full-size WebP and 640w / 960w resized variants."""
    try:
        img = Image.fromarray(rgb)
        # Save full-size WebP
        img.save(base_path.with_suffix(".webp"), "WEBP", quality=90, method=6)

        # Save resized variants preserving aspect ratio
        for width in (640, 960):
            ratio = width / img.width
            height = max(1, int(round(img.height * ratio)))
            resized = img.resize((width, height), Image.Resampling.LANCZOS)
            resized.save(
                base_path.parent / f"{base_path.stem}-{width}.webp",
                "WEBP",
                quality=85,
                method=6,
            )
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Failed to save image variants to {base_path}: {exc}") from exc


def _group_features_by_date(features: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for f in features:
        date = f["properties"]["datetime"][:10]
        groups.setdefault(date, []).append(f)
    return groups


def _covers_bbox(features: list[dict], bbox: list[float]) -> bool:
    """Return True if the union of feature bboxes contains the given bbox."""
    if not features:
        return False
    min_lon = min(f["bbox"][0] for f in features)
    min_lat = min(f["bbox"][1] for f in features)
    max_lon = max(f["bbox"][2] for f in features)
    max_lat = max(f["bbox"][3] for f in features)
    return _contains_bbox([min_lon, min_lat, max_lon, max_lat], bbox)


def process_site(site_key: str, site: dict) -> None:
    """Generate recent and older satellite images for a site."""
    label = site["label"]
    bbox = site["bbox"]
    width_px, height_px = bbox_metrics(bbox)
    is_mosaic = site.get("mosaic", False)
    print(f"\n{label}")
    print(f"  bbox: {bbox}")
    print(f"  target size: {width_px}x{height_px}px")
    if is_mosaic:
        print("  mosaic: True")

    for period, date_range in (("recent", site["recent_range"]), ("older", site["older_range"])):
        print(f"  Searching {period} scenes {date_range[0]} to {date_range[1]} ...")
        features = search_sentinel2(bbox, date_range, max_cloud=30.0, require_contain=not is_mosaic)
        if not features:
            print(f"  No {period} scenes found with <30% cloud cover; trying <60% ...")
            features = search_sentinel2(bbox, date_range, max_cloud=60.0, require_contain=not is_mosaic)
        if not features:
            print(f"  ERROR: No {period} scenes found.")
            continue

        if is_mosaic:
            # For mosaics, group by date and pick the date whose combined tiles cover the AOI.
            date_groups = _group_features_by_date(features)
            sorted_dates = sorted(
                date_groups.items(),
                key=lambda item: max(f["properties"].get("eo:cloud_cover", 100) for f in item[1]),
            )
            chosen_features = None
            chosen_date = None
            chosen_cloud = None
            for date, group in sorted_dates:
                # Prefer the group with the fewest tiles that still covers the bbox.
                candidates = []
                for f in group:
                    # Only include tiles that actually intersect the AOI.
                    if not (
                        f["bbox"][0] > bbox[2]
                        or f["bbox"][2] < bbox[0]
                        or f["bbox"][1] > bbox[3]
                        or f["bbox"][3] < bbox[1]
                    ):
                        candidates.append(f)
                if _covers_bbox(candidates, bbox):
                    chosen_features = candidates
                    chosen_date = date
                    chosen_cloud = max(f["properties"].get("eo:cloud_cover", 0.0) for f in candidates)
                    break
            if chosen_features is None:
                print("  ERROR: Could not find a date with full AOI coverage.")
                continue

            print(f"    Trying mosaic {chosen_date} (max cloud {chosen_cloud:.1f}%) ...", end=" ")
            try:
                result = render_mosaic(chosen_features, bbox, (height_px, width_px))
                if result is None:
                    print("too much no-data coverage")
                    continue
                rgb, date, cloud = result
                print("ok")
            except Exception as exc:
                print(f"failed ({exc})")
                continue
        else:
            # For recent images prefer the least cloudy scene, then the newest date.
            # For older images prefer the least cloudy scene, then the earliest date.
            def _date_int(feature: dict) -> int:
                return int(feature["properties"]["datetime"][:10].replace("-", ""))

            if period == "recent":
                features.sort(key=lambda f: (f["properties"].get("eo:cloud_cover", 100), -_date_int(f)))
            else:
                features.sort(key=lambda f: (f["properties"].get("eo:cloud_cover", 100), _date_int(f)))

            for feature in features:
                date = feature["properties"]["datetime"][:10]
                cloud = feature["properties"].get("eo:cloud_cover", 0.0)
                print(f"    Trying scene {date} (cloud {cloud:.1f}%) ...", end=" ")
                try:
                    result = render_scene(feature, bbox, (height_px, width_px))
                    if result is None:
                        print("too much no-data coverage")
                        continue
                    rgb, date, cloud = result
                    print("ok")
                    break
                except Exception as exc:
                    print(f"failed ({exc})")
                    continue
            else:
                print(f"  ERROR: Could not render any {period} scene.")
                continue

        base_name = f"{site_key}-{period}-{date}"
        base_path = OUT_DIR / base_name
        save_variants(rgb, base_path)
        print(f"saved {base_name}.webp / -640.webp / -960.webp")


def main() -> int:
    print("Generating Sentinel-2 satellite image candidates ...")
    for site_key, site in SITES.items():
        process_site(site_key, site)

    print(f"\nDone. Candidates written to: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
