"""Configuration and constants for citation processing."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import FrozenSet


# Metadata keys that are safe to surface in citation payloads.
SAFE_METADATA_FIELDS: FrozenSet[str] = frozenset({
    "file_name", "original_filename", "parent_doc", "source", "page_number",
    "section", "registry", "category", "document_id", "version_number", "title",
    "publisher", "registry_document_id", "methodology_codes",
})


_ALL_KB_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".json", ".jsonl",
    ".xml", ".yaml", ".yml", ".xlsx", ".xls", ".ppt", ".pptx", ".parquet",
    ".rst",
}

_EXTENSION_STRIP_RE = re.compile(
    r"\.(" + "|".join(re.escape(ext.lstrip(".")) for ext in _ALL_KB_EXTENSIONS) + r")$",
    re.IGNORECASE,
)

_KNOWN_SOURCE_ACRONYMS = {
    "ar6", "wg1", "wg2", "wg3", "ipcc", "vcs", "ghg", "co2",
    "cdm", "ndc", "redd", "mrv", "ets", "ets-2", "unfccc",
    "vm", "arr", "ams", "acm", "ccqi",
}

_TITLE_CASE_LOWER = frozenset({
    "a", "an", "the", "and", "but", "or", "nor", "for", "in", "on",
    "at", "to", "of", "by", "as", "is", "if", "vs",
})

_WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\n<>\"|?*]+")
_UNIX_PATH_RE = re.compile(r"/(?:home|root|usr|var|etc|tmp|opt|srv|mnt|proc)/[^\n<>\"|?*]+")
_ENV_PATH_RE = re.compile(r"\b[A-Z_]{3,}=(?:/[^\"]*\S|[A-Za-z]:\\[^\s]+)")

_WORD_COUNT_RE = re.compile(r"\b\w+\b")
_NON_ALNUM_SPACE_RE = re.compile(r"[^a-z0-9\s]")
_MULTISPACE_RE = re.compile(r"\s+")
_REPEATED_CHAR_RE = re.compile(r"(.)\1{2,}")
_VERSION_TOKEN_RE = re.compile(r"^v?\d+(?:\.\d+)*$", re.IGNORECASE)
_METHODOLOGY_ID_RE = re.compile(r"^(VM|VCS|ACM|AMS|CCQI)\d+(?:\.\d+)*$", re.IGNORECASE)
_VERSION_PREFIX_RE = re.compile(r"^(?:\d+_)?(v[\d.]+)_", re.IGNORECASE)
_NUMERIC_PREFIX_RE = re.compile(r"^\d+_(?=[A-Za-z])")
_SOURCE_PREFIX_RE = re.compile(r"^(?:\./|\.\\)?(?:data|documents|uploads|files|sources)[\\/]", re.IGNORECASE)
_FORMATTING_SEP_RE = re.compile(r"[_\-%]+")
_ELONGATED_CONVERSATIONAL_RE = re.compile(r"(h+i+|he+y+|he+l+o+|yo+|su+p+|ok+|th+x+|by+e+)")
_GREETING_PREFIX_RE = re.compile(
    r"^(hi|hello|hey|howdy|hiya|good\s+(?:morning|afternoon|evening|day))\s*[,!.]*\s*"
)
_SELF_INTRO_RE = re.compile(
    r"(?:my name is|i am|i m|im|this is|call me)\s+\S+(?:\s+\S+){0,3}"
)
_GREETING_FOLLOWUP_RE = re.compile(
    r"(?:there|everyone|team|all|cora|assistant|friend|folks"
    r"|my name is|i am|i m|im|this is|call me)(?:\s+\S+){0,3}"
)

_TRIVIAL_ANSWER_PATTERNS = (
    re.compile(r"\b(?:glad|happy)\s+to\s+(?:help|assist)\b"),
    re.compile(r"\bhow\s+can\s+i\s+(?:help|assist)\b"),
    re.compile(r"\bwhat\s+would\s+you\s+like\b"),
)

_EXACT_CONVERSATIONAL = frozenset({
    "hi there",
    "hi there how are you",
    "hi there how are you doing",
    "hey there",
    "hello there", "hello", "hey", "hola", "bonjour", "greetings", "howdy", "hiya",
    "good morning", "good afternoon", "good evening", "good day",
    "how are you", "how are you doing", "how is it going",
    "whats up", "what s up", "sup", "yo",
    "thanks", "thank you", "thanks a lot", "thank you so much",
    "thanks for the help", "thanks for your help", "thx", "ty",
    "ok", "okay", "got it", "understood", "noted",
    "sounds good", "no worries", "all good", "cool", "great", "nice",
    "bye", "goodbye", "see you", "see you later", "later", "cheers",
    "take care", "have a good day", "have a nice day",
    "test", "testing", "asdf",
    "what can you do", "who are you", "what are you",
    "what is your name", "are you a bot", "are you an ai",
    "help", "help me", "how can you help", "how can you help me",
    "tell me about yourself", "introduce yourself",
    "can you hear me", "are you there",
})


@dataclass(frozen=True)
class CitationConfig:
    """Configurable thresholds and limits for citation logic."""

    snippet_max_length: int = 200
    short_answer_char_limit: int = 50
    coverage_suppression_threshold: float = 0.2
    kb_extensions: FrozenSet[str] = field(default_factory=lambda: frozenset(_ALL_KB_EXTENSIONS))
