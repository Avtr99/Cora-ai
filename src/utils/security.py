"""
Security utilities for path validation and input sanitization.

This module provides functions to prevent path traversal attacks,
validate file paths, and ensure the integrity of conversation history
via HMAC signatures.
"""
import os
import re
import hmac
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, List, Dict


logger = logging.getLogger(__name__)


def validate_path(
    path: str,
    allowed_base_dirs: List[str],
    allow_absolute: bool = False
) -> str:
    """
    Validate and sanitize a file path to prevent path traversal attacks.
    
    This function enforces mandatory directory restrictions to prevent
    unauthorized filesystem access. All paths must be within one of the
    specified allowed base directories.
    
    Args:
        path: The path to validate
        allowed_base_dirs: List of allowed base directories. The resolved path
                          MUST be within one of these directories. This parameter
                          is mandatory to ensure path traversal protection.
        allow_absolute: Whether to allow absolute paths. If False, only relative
                       paths are accepted.
    
    Returns:
        The validated and resolved absolute path
        
    Raises:
        ValueError: If the path is invalid or attempts path traversal
    """
    if not path:
        raise ValueError("Path cannot be empty")
    
    if not allowed_base_dirs:
        raise ValueError("allowed_base_dirs must be provided for security")
    
    # Normalize the path to resolve .. and . components
    normalized = os.path.normpath(path)
    
    # Check for null bytes (common attack vector)
    if '\x00' in path:
        raise ValueError("Null bytes not allowed in path")
    
    # If absolute paths not allowed, check
    if not allow_absolute and os.path.isabs(path):
        raise ValueError("Absolute paths not allowed")
    
    # Resolve to absolute path
    resolved = os.path.abspath(normalized)
    
    # Verify path is within one of the allowed base directories
    is_allowed = False
    for base_dir in allowed_base_dirs:
        base_resolved = os.path.abspath(base_dir)
        try:
            # Use Path.relative_to to check if resolved is under base_resolved
            Path(resolved).relative_to(base_resolved)
            is_allowed = True
            break
        except ValueError:
            continue
    
    if not is_allowed:
        raise ValueError(
            f"Path '{path}' is not within allowed directories"
        )
    
    return resolved


def validate_file_path(
    file_path: str,
    allowed_base_dirs: List[str],
    allowed_extensions: Optional[List[str]] = None,
    must_exist: bool = True
) -> str:
    """
    Validate a file path with additional file-specific checks.
    
    Args:
        file_path: The file path to validate
        allowed_base_dirs: List of allowed base directories (mandatory for security)
        allowed_extensions: List of allowed file extensions (e.g., ['.txt', '.md'])
        must_exist: Whether the file must exist
        
    Returns:
        The validated and resolved absolute file path
        
    Raises:
        ValueError: If the path is invalid
        FileNotFoundError: If must_exist is True and file doesn't exist
    """
    # First validate the path
    resolved = validate_path(
        file_path,
        allowed_base_dirs=allowed_base_dirs,
        allow_absolute=True  # Allow absolute for file operations
    )
    
    # Check file extension if specified
    if allowed_extensions:
        ext = os.path.splitext(resolved)[1].lower()
        if ext not in [e.lower() for e in allowed_extensions]:
            raise ValueError(
                f"File extension '{ext}' not allowed. "
                f"Allowed: {allowed_extensions}"
            )
    
    # Check if file exists if required
    if must_exist and not os.path.isfile(resolved):
        raise FileNotFoundError(f"File not found: {resolved}")
    
    return resolved


def validate_directory_path(
    dir_path: str,
    allowed_base_dirs: List[str],
    must_exist: bool = True
) -> str:
    """
    Validate a directory path with additional directory-specific checks.
    
    Args:
        dir_path: The directory path to validate
        allowed_base_dirs: List of allowed base directories (mandatory for security)
        must_exist: Whether the directory must exist
        
    Returns:
        The validated and resolved absolute directory path
        
    Raises:
        ValueError: If the path is invalid
        NotADirectoryError: If must_exist is True and path is not a directory
    """
    # First validate the path
    resolved = validate_path(
        dir_path,
        allowed_base_dirs=allowed_base_dirs,
        allow_absolute=True  # Allow absolute for directory operations
    )
    
    # Check if directory exists if required
    if must_exist:
        if not os.path.exists(resolved):
            raise FileNotFoundError(f"Directory not found: {resolved}")
        if not os.path.isdir(resolved):
            raise NotADirectoryError(f"Path is not a directory: {resolved}")
    
    return resolved


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to remove potentially dangerous characters.
    
    Args:
        filename: The filename to sanitize
        
    Returns:
        Sanitized filename safe for filesystem operations
    """
    if not filename:
        raise ValueError("Filename cannot be empty")
    
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove null bytes
    filename = filename.replace('\x00', '')
    
    # Remove other potentially dangerous characters
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    
    # Prevent hidden files on Unix
    if filename.startswith('.'):
        filename = '_' + filename[1:]
    
    # Limit length
    max_length = 255
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        filename = name[:max_length - len(ext)] + ext
    
    return filename


# Patterns for sensitive data in error messages
_SENSITIVE_PATTERNS = [
    (re.compile(r'https?://[^\s,\'")\]]+'), '[redacted-url]'),
    (re.compile(r'(?:[A-Za-z]:)?(?:[/\\][\w.\-]+){2,}'), '[redacted-path]'),
    (re.compile(r'(?:key|token|secret|password|apikey|api_key)[=:\s]+\S+', re.IGNORECASE), '[redacted-credential]'),
    (re.compile(r'(?:mongodb|postgres|mysql|redis)://\S+', re.IGNORECASE), '[redacted-connection-string]'),
    (re.compile(r'\b[A-Za-z0-9+/]{40,}={0,2}\b'), '[redacted-token]'),
]


def sanitize_error_message(error: str, context: str = "internal error") -> str:
    """
    Sanitize an error message by stripping sensitive details.

    Removes file paths, URLs, tokens, connection strings and other
    potentially sensitive substrings. Returns a generic message with
    only the exception type preserved for debugging.

    Args:
        error: Raw error string (typically str(e) from an exception)
        context: Short description of where the error occurred

    Returns:
        Sanitized error string safe for user-facing step details
    """
    if not error:
        return f"Internal error during {context}"

    # Extract exception class name if present (e.g. "ConnectionError: ...")
    exc_type = ""
    if ":" in error:
        potential_type = error.split(":")[0].strip()
        if re.match(r'^[A-Za-z_]\w*(?:Error|Exception|Timeout|Failure)$', potential_type):
            exc_type = potential_type

    sanitized = error
    for pattern, replacement in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)

    # Trim to a reasonable length
    if len(sanitized) > 120:
        sanitized = sanitized[:120] + "..."

    summary = f"Internal error during {context}"
    if exc_type:
        summary += f" ({exc_type})"

    return summary


def sign_history(
    history: List[Dict[str, str]], 
    conversation_id: str, 
    secret_key: str,
    scope_key: str = "",
    *,
    allow_unsigned: bool = False,
) -> str:
    """
    Sign conversation history, conversation ID, and scope using HMAC-SHA256.
    
    This ensures that:
    1. History cannot be tampered with by the client.
    2. History cannot be swapped between different conversations.
    3. History is bound to the specific user/session scope if provided.
    
    Args:
        history: List of messages (role, content)
        conversation_id: Unique ID for the conversation
        secret_key: Secret key for signing
        scope_key: Optional scope identifier (e.g., user_id or session_id)
        
    Returns:
        HMAC signature as a hexadecimal string. Only the message role/content
        fields are included in the canonical payload; any additional keys on
        history entries are ignored to keep signatures stable.
    """
    if not secret_key:
        message = (
            "Attempted to sign history but SECRET_KEY is not configured. "
            "History signatures cannot be generated securely."
        )
        if allow_unsigned:
            logger.warning(f"{message} Returning 'unsigned' placeholder for dev mode.")
            return "unsigned"
        raise RuntimeError(message)
        
    # Canonicalize the history to ensure stable signatures
    canonical_history = [
        {"role": m.get("role", ""), "content": m.get("content", "")}
        for m in history
    ]
    
    # Include conversation_id and scope in the payload to bind history
    payload = {
        "history": canonical_history,
        "conversation_id": conversation_id,
        "scope": scope_key if scope_key else "anonymous"
    }
    
    payload_json = json.dumps(payload, sort_keys=True)
    
    return hmac.new(
        secret_key.encode(),
        payload_json.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_history_signature(
    history: List[Dict[str, str]], 
    conversation_id: str, 
    signature: str, 
    secret_key: str,
    scope_key: str = ""
) -> bool:
    """
    Verify the HMAC signature of conversation history, ID, and scope.
    
    Args:
        history: List of messages
        conversation_id: Unique ID for the conversation
        signature: Hexadecimal signature to verify
        secret_key: Secret key for signing
        scope_key: Optional scope identifier
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not signature or not secret_key:
        return False
    if signature == "unsigned":
        return False
        
    expected_signature = sign_history(history, conversation_id, secret_key, scope_key)
    return hmac.compare_digest(expected_signature, signature)
