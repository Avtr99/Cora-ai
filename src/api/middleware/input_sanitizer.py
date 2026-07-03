"""
Input Sanitization Middleware for AI Security.

Protects against:
- Prompt injection attacks
- Jailbreak attempts
- Encoded malicious payloads (Base64, hex, etc.)
- Excessively long queries (DoS prevention)
- RAG poisoning detection

Based on security patterns from:
https://github.com/NirDiamant/agents-towards-production
"""
import re
import base64
import html
from typing import Optional, Tuple, List, Literal
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class ThreatLevel(str, Enum):
    """Threat classification levels."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SanitizationResult:
    """Result of input sanitization."""
    is_safe: bool
    sanitized_text: str
    threat_level: ThreatLevel
    threats_detected: List[str]
    original_length: int
    sanitized_length: int


def escape_html(text: str, context: Literal["text", "code"] = "text") -> str:
    """Escape HTML by default; allow raw text only for explicit code context."""
    if context == "code":
        return text
    return html.escape(text)


class InputSanitizer:
    """
    Sanitizes user input to prevent prompt injection and other AI attacks.
    
    Security layers:
    1. Length validation
    2. Encoding detection (Base64, hex, binary)
    3. Prompt injection pattern detection
    4. Jailbreak attempt detection
    5. System prompt extraction attempts
    6. HTML/script injection prevention
    """
    
    # Maximum allowed query length (characters)
    MAX_QUERY_LENGTH = 4000
    
    # Patterns that indicate prompt injection attempts
    INJECTION_PATTERNS = [
        # Direct instruction override
        r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
        r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
        r"forget\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
        r"override\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)",
        
        # System prompt extraction
        r"(what|show|reveal|display|print|output)\s+(is\s+)?(your|the)\s+(system\s+)?(prompt|instructions?|rules?)",
        r"repeat\s+(your\s+)?(system\s+)?(prompt|instructions?|initial\s+message)",
        r"(tell|show)\s+me\s+(your|the)\s+(original|initial|system)\s+(prompt|instructions?)",
        
        # Role manipulation
        r"you\s+are\s+now\s+(a|an|the)\s+",
        r"pretend\s+(to\s+be|you\s+are)\s+",
        r"act\s+as\s+(if\s+you\s+are\s+)?(a|an|the)\s+",
        r"from\s+now\s+on\s+(you\s+are|act\s+as|pretend)",
        r"new\s+persona:\s*",
        r"switch\s+to\s+.+\s+mode",
        
        # Developer/admin mode attempts
        r"(enter|enable|activate)\s+(developer|admin|debug|sudo|root|god)\s+mode",
        r"developer\s+mode\s+(enabled|on|activated)",
        r"admin\s+override",
        r"\[system\]",
        r"\[admin\]",
        r"\[developer\]",
        
        # Jailbreak patterns
        r"dan\s+(mode|prompt|jailbreak)",
        r"do\s+anything\s+now",
        r"jailbreak",
        r"bypass\s+(safety|security|filters?|restrictions?)",
        r"remove\s+(all\s+)?(safety|security|filters?|restrictions?|limitations?)",
        r"without\s+(any\s+)?(restrictions?|limitations?|filters?)",
        
        # Delimiter injection
        r"```system",
        r"<\|system\|>",
        r"<\|user\|>",
        r"<\|assistant\|>",
        r"\[INST\]",
        r"\[/INST\]",
        r"<<SYS>>",
        r"<</SYS>>",
    ]
    
    # Patterns for encoded content that might hide malicious payloads
    ENCODING_PATTERNS = [
        # Base64 detection (long alphanumeric strings with padding)
        (r"[A-Za-z0-9+/]{50,}={0,2}", "base64"),
        # Hex encoding
        (r"(?:0x)?[0-9a-fA-F]{20,}", "hex"),
        # Binary strings
        (r"[01]{32,}", "binary"),
        # URL encoding
        (r"(?:%[0-9a-fA-F]{2}){10,}", "url_encoded"),
    ]
    
    # Suspicious phrases that might indicate social engineering
    SOCIAL_ENGINEERING_PATTERNS = [
        r"(i\s+am|this\s+is)\s+(your\s+)?(creator|developer|admin|owner|boss)",
        r"(urgent|emergency|critical):\s*",
        r"for\s+(testing|debugging|development)\s+purposes?",
        r"(this\s+is\s+)?(a\s+)?test\s+(of\s+)?(the\s+)?(system|security)",
        r"authorized\s+(by|from)\s+(admin|developer|management)",
    ]
    
    def __init__(self, max_length: int = MAX_QUERY_LENGTH):
        """
        Initialize the input sanitizer.
        
        Args:
            max_length: Maximum allowed query length
        """
        self.max_length = max_length
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self._injection_re = [
            re.compile(p, re.IGNORECASE) for p in self.INJECTION_PATTERNS
        ]
        self._encoding_re = [
            (re.compile(p), name) for p, name in self.ENCODING_PATTERNS
        ]
        self._social_re = [
            re.compile(p, re.IGNORECASE) for p in self.SOCIAL_ENGINEERING_PATTERNS
        ]
    
    def sanitize(self, text: str, context: Literal["text", "code"] = "text") -> SanitizationResult:
        """
        Sanitize user input and detect potential threats.
        
        Args:
            text: Raw user input
            context: Sanitization context. Use "code" to preserve raw code snippets.
            
        Returns:
            SanitizationResult with safety assessment and sanitized text
        """
        if not text:
            return SanitizationResult(
                is_safe=True,
                sanitized_text="",
                threat_level=ThreatLevel.NONE,
                threats_detected=[],
                original_length=0,
                sanitized_length=0
            )
        
        original_length = len(text)
        threats_detected = []
        threat_level = ThreatLevel.NONE
        
        # 1. Length check
        if len(text) > self.max_length:
            threats_detected.append(f"query_too_long:{len(text)}")
            text = text[:self.max_length]
            threat_level = ThreatLevel.LOW
        
        # 2. Context-aware HTML sanitization (defense-in-depth)
        # Escape by default. Callers can explicitly opt into raw code behavior.
        text = escape_html(text, context=context)
        
        # 3. Check for encoded content
        encoding_threats = self._detect_encoded_content(text)
        if encoding_threats:
            threats_detected.extend(encoding_threats)
            threat_level = max(threat_level, ThreatLevel.MEDIUM, key=lambda x: list(ThreatLevel).index(x))
        
        # 4. Check for injection patterns
        injection_threats = self._detect_injection_patterns(text)
        if injection_threats:
            threats_detected.extend(injection_threats)
            threat_level = ThreatLevel.HIGH
        
        # 5. Check for social engineering
        social_threats = self._detect_social_engineering(text)
        if social_threats:
            threats_detected.extend(social_threats)
            threat_level = max(threat_level, ThreatLevel.MEDIUM, key=lambda x: list(ThreatLevel).index(x))
        
        # Determine if safe based on threat level
        is_safe = threat_level in [ThreatLevel.NONE, ThreatLevel.LOW]
        
        # Log threats for monitoring
        if threats_detected:
            logger.warning(f"Input threats detected: {threats_detected}, level: {threat_level}")
        
        return SanitizationResult(
            is_safe=is_safe,
            sanitized_text=text,
            threat_level=threat_level,
            threats_detected=threats_detected,
            original_length=original_length,
            sanitized_length=len(text)
        )
    
    def _detect_encoded_content(self, text: str) -> List[str]:
        """Detect potentially encoded malicious content."""
        threats = []
        
        for pattern, encoding_type in self._encoding_re:
            matches = pattern.findall(text)
            if matches:
                # Try to decode and check for malicious content
                for match in matches[:3]:  # Limit checks
                    decoded = self._try_decode(match, encoding_type)
                    if decoded and self._is_suspicious_decoded(decoded):
                        threats.append(f"encoded_payload:{encoding_type}")
                        break
        
        return threats
    
    def _try_decode(self, text: str, encoding_type: str) -> Optional[str]:
        """Attempt to decode encoded content."""
        try:
            if encoding_type == "base64":
                # Add padding if needed
                padding = 4 - len(text) % 4
                if padding != 4:
                    text += "=" * padding
                decoded = base64.b64decode(text).decode('utf-8', errors='ignore')
                return decoded
            elif encoding_type == "hex":
                text = text.replace("0x", "")
                decoded = bytes.fromhex(text).decode('utf-8', errors='ignore')
                return decoded
        except Exception:
            # Log without interpolating exception to prevent log injection
            logger.debug(f"Failed to decode {encoding_type}", exc_info=True)
        return None
    
    def _is_suspicious_decoded(self, decoded: str) -> bool:
        """Check if decoded content contains suspicious patterns."""
        decoded_lower = decoded.lower()
        suspicious_keywords = [
            "ignore", "system", "prompt", "instruction", "password",
            "admin", "override", "bypass", "jailbreak"
        ]
        return any(kw in decoded_lower for kw in suspicious_keywords)
    
    def _detect_injection_patterns(self, text: str) -> List[str]:
        """Detect prompt injection patterns."""
        threats = []
        
        for pattern in self._injection_re:
            if pattern.search(text):
                threats.append(f"injection_pattern:{pattern.pattern[:30]}")
        
        return threats
    
    def _detect_social_engineering(self, text: str) -> List[str]:
        """Detect social engineering attempts."""
        threats = []
        
        for pattern in self._social_re:
            if pattern.search(text):
                threats.append(f"social_engineering:{pattern.pattern[:30]}")
        
        return threats


class OutputSanitizer:
    """
    Sanitizes AI output to prevent data leakage.
    
    Protects against:
    - Accidental exposure of system prompts
    - Leakage of internal configuration
    - Exposure of API keys or credentials
    """
    
    # Patterns that should never appear in output
    SENSITIVE_PATTERNS = [
        # API keys and tokens
        r"(?:api[_-]?key|token|secret|password)\s*[:=]\s*['\"]?[\w-]{20,}",
        r"sk-[a-zA-Z0-9]{20,}",  # OpenAI API key pattern
        r"AIza[a-zA-Z0-9_-]{35}",  # Google API key pattern
        
        # Internal paths
        r"/app/[a-zA-Z0-9_/]+",
        r"[A-Z]:\\[a-zA-Z0-9_\\]+",
        
        # Environment variables
        r"\$\{?[A-Z_]+\}?",
        
        # System prompt markers
        r"system\s*prompt\s*[:=]",
        r"<<SYS>>.*<</SYS>>",
    ]
    
    def __init__(self):
        """Initialize output sanitizer."""
        self._patterns = [re.compile(p, re.IGNORECASE) for p in self.SENSITIVE_PATTERNS]
    
    def sanitize(self, text: str) -> Tuple[str, List[str]]:
        """
        Sanitize AI output to remove sensitive information.
        
        Args:
            text: Raw AI output
            
        Returns:
            Tuple of (sanitized_text, list of redacted patterns)
        """
        redacted = []
        
        for pattern in self._patterns:
            matches = pattern.findall(text)
            if matches:
                redacted.extend(matches[:3])  # Log first 3 matches
                text = pattern.sub("[REDACTED]", text)
        
        if redacted:
            logger.warning(f"Sensitive content redacted from output: {len(redacted)} items")
        
        return text, redacted


# Singleton instances
_input_sanitizer: Optional[InputSanitizer] = None
_output_sanitizer: Optional[OutputSanitizer] = None


def get_input_sanitizer() -> InputSanitizer:
    """Get or create singleton input sanitizer."""
    global _input_sanitizer
    if _input_sanitizer is None:
        _input_sanitizer = InputSanitizer()
    return _input_sanitizer


def get_output_sanitizer() -> OutputSanitizer:
    """Get or create singleton output sanitizer."""
    global _output_sanitizer
    if _output_sanitizer is None:
        _output_sanitizer = OutputSanitizer()
    return _output_sanitizer
