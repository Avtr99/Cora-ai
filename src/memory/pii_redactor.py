"""
PII detection and redaction for conversation memory.

Detects and redacts personally identifiable information before storage
to comply with GDPR and privacy best practices.

Note: Regex-based detection catches common patterns (emails, phones, SSNs)
but may miss context-dependent PII (names, addresses). For production systems
handling sensitive data, consider integrating a dedicated PII service.
"""
import re
import threading
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from loguru import logger

from ..utils.pii_patterns import EMAIL_RE, IP_ADDRESS_RE, UUID_RE


@dataclass
class PIIPattern:
    """Definition of a PII pattern to detect."""
    name: str
    pattern: re.Pattern
    replacement: str
    description: str


# Default PII patterns (GDPR-relevant)
# Order matters: more specific patterns must come before general ones
DEFAULT_PII_PATTERNS: List[PIIPattern] = [
    # Most specific patterns first
    PIIPattern(
        name="ssn_us",
        pattern=re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        replacement="[SSN]",
        description="US Social Security Numbers",
    ),
    PIIPattern(
        name="credit_card",
        pattern=re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
        replacement="[CARD]",
        description="Credit card numbers",
    ),
    PIIPattern(
        name="iban",
        pattern=re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}[A-Z0-9]{0,16}\b'),
        replacement="[IBAN]",
        description="IBAN account numbers",
    ),
    PIIPattern(
        name="email",
        # Shared regex from utils.pii_patterns to avoid duplication with citation sanitization.
        pattern=EMAIL_RE,
        replacement="[EMAIL]",
        description="Email addresses",
    ),
    # Phone patterns - US format is more specific, check before international
    PIIPattern(
        name="phone_us",
        pattern=re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
        replacement="[PHONE]",
        description="US phone numbers",
    ),
    PIIPattern(
        name="phone_intl",
        pattern=re.compile(r'\b\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b'),
        replacement="[PHONE]",
        description="International phone numbers (with country code)",
    ),
    # IP address - must come after phone patterns to avoid false matches
    PIIPattern(
        name="ip_address",
        pattern=IP_ADDRESS_RE,
        replacement="[IP]",
        description="IPv4 addresses",
    ),
    PIIPattern(
        name="uuid",
        pattern=UUID_RE,
        replacement="[ID]",
        description="UUIDs (may contain user identifiers)",
    ),
]


@dataclass
class RedactionResult:
    """Result of PII redaction operation."""
    redacted_text: str
    detections: Dict[str, int] = field(default_factory=dict)
    
    @property
    def total_detections(self) -> int:
        """Total number of PII detections (computed from detections dict)."""
        return sum(self.detections.values())
    
    @property
    def has_pii(self) -> bool:
        """Check if any PII was detected."""
        return self.total_detections > 0


class PIIRedactor:
    """
    Detect and redact PII before memory storage.
    
    Uses pattern-based detection for common PII types. Can be extended
    with custom patterns or integrated with dedicated PII services.
    
    Example:
        >>> redactor = PIIRedactor()
        >>> result = redactor.redact("Contact me at john@example.com")
        >>> print(result.redacted_text)
        "Contact me at [EMAIL]"
        >>> print(result.detections)
        {"email": 1}
    """
    
    def __init__(
        self,
        patterns: Optional[List[PIIPattern]] = None,
        enabled: bool = True,
        log_detections: bool = True,
    ):
        """
        Initialize PII redactor.
        
        Args:
            patterns: Custom patterns (defaults to DEFAULT_PII_PATTERNS)
            enabled: Whether redaction is active
            log_detections: Whether to log detection counts (not content)
        """
        self.patterns = list(patterns) if patterns is not None else list(DEFAULT_PII_PATTERNS)
        self.enabled = enabled
        self.log_detections = log_detections
    
    def redact(self, text: str) -> RedactionResult:
        """
        Detect and redact PII in text.
        
        Args:
            text: Input text to scan for PII
            
        Returns:
            RedactionResult with redacted text and detection counts
        """
        if not self.enabled or not text:
            return RedactionResult(redacted_text=text)
        
        redacted_text = text
        detections: Dict[str, int] = {}
        
        for pii_pattern in self.patterns:
            # Single-pass substitution with count; re.subn returns (new_text, count)
            redacted_text, count = pii_pattern.pattern.subn(
                pii_pattern.replacement, redacted_text
            )
            if count:
                detections[pii_pattern.name] = count
        
        
        if self.log_detections and detections:
            # Log counts only, never log actual PII content
            logger.info(
                f"PII redacted: total={sum(detections.values())}, types={detections}"
            )
        
        return RedactionResult(
            redacted_text=redacted_text,
            detections=detections,
        )
    
    def redact_dict(
        self,
        data: Dict[str, str],
        keys_to_redact: Optional[List[str]] = None,
    ) -> Tuple[Dict[str, str], RedactionResult]:
        """
        Redact PII in dictionary values.
        
        Args:
            data: Dictionary with string values
            keys_to_redact: Specific keys to process (defaults to all string values)
            
        Returns:
            Tuple of (redacted dict, combined result)
        """
        if not self.enabled:
            return data.copy(), RedactionResult(redacted_text="")
        
        result = data.copy()
        combined_detections: Dict[str, int] = {}
        
        for key, value in result.items():
            if keys_to_redact and key not in keys_to_redact:
                continue
            if not isinstance(value, str):
                continue
            
            redaction = self.redact(value)
            if redaction.has_pii:
                result[key] = redaction.redacted_text
                for pii_type, count in redaction.detections.items():
                    combined_detections[pii_type] = combined_detections.get(pii_type, 0) + count
        
        return result, RedactionResult(
            redacted_text="",
            detections=combined_detections,
        )


# Singleton instance for default usage
_redactor: Optional[PIIRedactor] = None
_redactor_lock = threading.Lock()


def get_pii_redactor() -> PIIRedactor:
    """
    Get or create the singleton PII redactor (thread-safe).

    Returns:
        PIIRedactor instance
    """
    global _redactor
    if _redactor is None:
        with _redactor_lock:
            if _redactor is None:
                from ..config import get_settings
                settings = get_settings()
                _redactor = PIIRedactor(
                    enabled=getattr(settings, 'PII_REDACTION_ENABLED', True),
                    log_detections=True,
                )
    return _redactor
