#!/usr/bin/env python3
"""Download only the models the standard Docling route needs.

Called during Docker build to prebake models into the image. Downloads:
  - Layout model (docling-layout-heron or -onnx, ~164MB — engine per
    DOCLING_LAYOUT_ENGINE, matching DOCUMENT_DOCLING_LAYOUT_ENGINE)
  - TableFormer (docling-models, ~342MB, both accurate + fast variants)
  - RapidOCR models (PP-OCR, ~31MB, onnxruntime backend, english + chinese)

Skips:
  - The layout repo for the engine NOT in use (~164MB). If the runtime
    engine is changed later, the matching repo must be fetched separately.
  - The VLM models download_models() would pull by default:
    Picture classifier  — do_picture_description=False
    CodeFormulaV2 (~610MB) — do_formula_enrichment=False, crashes on CPU

Usage:
    DOCLING_LAYOUT_ENGINE=onnxruntime python download_docling_models.py /app/models/docling
"""
import os
import sys
from pathlib import Path

from docling.datamodel.pipeline_options import LayoutObjectDetectionOptions
from docling.datamodel.stage_model_specs import ObjectDetectionEngineType
from docling.models.utils.hf_model_download import download_hf_model
from docling.utils.model_downloader import download_models

output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/app/models/docling")
layout_engine = os.environ.get("DOCLING_LAYOUT_ENGINE", "onnxruntime").lower()

print(f"Downloading Docling models to {output_dir} (layout engine: {layout_engine}) ...")

# Layout: fetch only the repo for the configured engine. The full
# download_models() pulls every engine_overrides variant (~164MB each),
# but the pipeline only ever loads one.
layout_spec = LayoutObjectDetectionOptions().model_spec
repo_id, revision = layout_spec.repo_id, layout_spec.revision
if layout_engine != "transformers":
    engine_type = ObjectDetectionEngineType(layout_engine)
    override = layout_spec.engine_overrides.get(engine_type)
    if override is None:
        raise ValueError(
            f"Layout engine {layout_engine!r} has no repo override for the "
            f"default model. Valid engines: transformers | "
            + " | ".join(e.value for e in layout_spec.engine_overrides)
        )
    merged = override.merge_with(repo_id, revision)
    repo_id, revision = merged.repo_id, merged.revision

print(f"1/2: Layout model ({repo_id}) ...")
download_hf_model(
    repo_id=repo_id,
    revision=revision,
    local_dir=output_dir / repo_id.replace("/", "--"),
    progress=True,
)

print("2/2: TableFormer + RapidOCR ...")
download_models(
    output_dir=output_dir,
    progress=True,
    with_layout=False,
    with_tableformer=True,
    with_code_formula=False,
    with_picture_classifier=False,
    with_rapidocr=True,
    # <backend>:<lang> specs. English is the default for VCM docs; Chinese is
    # Docling's built-in default — both are prefetched so users who override
    # the language don't hit missing-model errors.
    rapidocr_models=["onnxruntime:en", "onnxruntime:ch"],
)

print("Done.")
