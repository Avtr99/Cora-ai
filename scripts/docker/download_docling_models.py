#!/usr/bin/env python3
"""Download only the models the standard Docling route needs.

Called during Docker build to prebake models into the image. Downloads:
  - Layout model (docling-layout-heron, ~327MB)
  - TableFormer (docling-models, ~342MB, both accurate + fast variants)
  - RapidOCR models (PP-OCRv4, ~30MB, onnxruntime backend, english + chinese)

Skips the VLM models that download_models() would pull by default:
  - Picture classifier  — do_picture_description=False
  - CodeFormulaV2 (~610MB) — do_formula_enrichment=False, crashes on CPU

Usage:
    python download_docling_models.py /app/models/docling
"""
import sys
from pathlib import Path

from docling.datamodel.pipeline_options import LayoutOptions
from docling.models.stages.layout.layout_model import LayoutModel
from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
from docling.models.stages.table_structure.table_structure_model import TableStructureModel

output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/app/models/docling")
output_dir.mkdir(parents=True, exist_ok=True)

print(f"Downloading Docling models to {output_dir} ...")

print("1/3: Layout model (docling-layout-heron, ~327MB) ...")
layout_dir = output_dir / LayoutOptions().model_spec.model_repo_folder
LayoutModel.download_models(local_dir=layout_dir, progress=True)
print(f"  -> {layout_dir}")

print("2/3: TableFormer (docling-models, ~342MB) ...")
tableformer_dir = output_dir / TableStructureModel._model_repo_folder
TableStructureModel.download_models(local_dir=tableformer_dir, progress=True)
print(f"  -> {tableformer_dir}")

print("3/3: RapidOCR models (PP-OCRv4, ~30MB) ...")
rapidocr_dir = output_dir / RapidOcrModel._model_repo_folder
# Download both English (default for VCM docs) and Chinese (Docling's built-in
# default) so users who override the language don't hit missing-model errors.
for lang in ("english", "chinese"):
    RapidOcrModel.download_models(
        backend="onnxruntime", local_dir=rapidocr_dir, progress=True, lang=lang
    )
print(f"  -> {rapidocr_dir}")

print("Done.")
