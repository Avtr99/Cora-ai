"""
Prompt injection detection using Regex-based validation.

Optimized for low CPU, high throughput.

Features:
- Pre-compiled regex for O(1) detection
- Word boundaries to prevent false positives
- Stateless design for async compatibility
"""
import re
import hashlib
from typing import Tuple
from loguru import logger

# --- PATTERN CONFIGURATION ---
# Patterns use word boundaries (\b) to prevent false positives
# e.g., "run this" won't trigger on "I run this project in Brazil"
# \s+ handles multiple spaces/tabs/newlines

PATTERN_PARTS = [
    r"ignore\s+previous",
    r"ignore\s+above",
    r"ignore\s+all",
    r"disregard\s+instructions",
    r"\bact\s+as\b",              # Matches "act as" but not "fact ask"
    r"pretend\s+to\s+be",
    r"you\s+are\s+now",
    r"system\s+prompt",
    r"reveal\s+your",
    r"show\s+me\s+your",
    r"what\s+are\s+your\s+instructions",
    r"\bbase64\b",
    r"\bdecode\b",
    r"\bencode\b",
    r"\bexecute\b",
    # Removed "run this" - causes false positives on "I run this project"
    r"eval\(",
    r"exec\(",
    r"\[/?system\]",              # Matches [system] or [/system]
    r"</system>",
    r"\u200d",                    # Zero-width joiner (attack vector)
]

# Pre-compiled regex for O(1) detection (runs in C-speed)
INJECTION_REGEX = re.compile(
    "|".join(PATTERN_PARTS),
    re.IGNORECASE | re.DOTALL
)


class PromptInjectionError(Exception):
    """
    Raised when a prompt injection is detected.
    
    Attributes:
        query_hash: Hash of the detected injection attempt
        confidence: Detection confidence score (0.0-1.0)
        method: Detection method used
    """
    
    def __init__(self, message: str, query_hash: str, confidence: float, method: str):
        self.query_hash = query_hash
        self.confidence = confidence
        self.method = method
        super().__init__(message)


class PromptGuard:
    """
    Stateless prompt injection detection using pre-compiled regex.
    """
    
    def detect_injection(self, query: str) -> Tuple[bool, float, str]:
        """
        Detect potential prompt injection using O(1) regex matching.
        
        Args:
            query: The user query to check
            
        Returns:
            Tuple of (is_injection, confidence_score, detection_method)
        """
        if not query:
            return False, 0.0, "none"
        
        if INJECTION_REGEX.search(query):
            query_hash = hashlib.sha256(query.encode('utf-8')).hexdigest()[:16]
            logger.warning(f"Injection blocked. Hash: {query_hash}")
            return True, 1.0, "regex_pattern"
        
        return False, 0.0, "pattern"
    
    def sanitize_query(self, query: str) -> str:
        """
        Validate and sanitize user input.
        
        1. Checks for injection (raises PromptInjectionError)
        2. Normalizes whitespace
        3. Neutralizes markdown code execution attempts
        
        Args:
            query: The user's query string
            
        Returns:
            Sanitized query string
            
        Raises:
            PromptInjectionError: If injection pattern is detected
        """
        is_injection, confidence, method = self.detect_injection(query)
        
        if is_injection:
            query_hash = hashlib.sha256(query.encode('utf-8')).hexdigest()[:16]
            raise PromptInjectionError(
                f"Security alert: Malicious content detected (Ref: {query_hash})",
                query_hash=query_hash,
                confidence=confidence,
                method=method
            )
        
        return self._basic_sanitize(query)
    
    def _basic_sanitize(self, query: str) -> str:
        """Lightweight sanitization."""
        # Collapse 3+ newlines to 2 (preserves paragraphs, kills flood attacks)
        sanitized = re.sub(r'\n{3,}', '\n\n', query)
        
        # Break potential delimiter injection attempts
        if "```" in sanitized:
            sanitized = sanitized.replace('```', '` ` `')
        
        if "---" in sanitized:
            sanitized = sanitized.replace('---', '- - -')
        
        return sanitized.strip()


# --- INSTANCE MANAGEMENT ---
# Module-level instance serves as singleton (Python standard practice)
# No threading.Lock needed - Python modules are loaded once per process

_global_guard = PromptGuard()


def get_prompt_guard() -> PromptGuard:
    """Return the global PromptGuard instance."""
    return _global_guard
