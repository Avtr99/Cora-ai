"""
Document metadata extraction package.

Production ingestion uses LangChain loaders in the local-only ingestion
pipeline (kept outside the deployed runtime). This package retains only the
shared metadata extraction logic that the production pipeline
(VCMMetadataEnhancer) depends on.
"""
from .metadata_extractor import MetadataExtractor, get_metadata_extractor

__all__ = [
    'MetadataExtractor',
    'get_metadata_extractor',
]