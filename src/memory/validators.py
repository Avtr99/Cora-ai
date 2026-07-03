"""
Validation utilities for conversation memory using Pydantic.

This module provides reusable Pydantic models and validation functions for:
- User and session ID format validation
- Metadata structure and size validation
- Pagination parameter validation

These validators can be reused across the codebase for consistent
input validation patterns.
"""
import json
from typing import Dict, Any, Optional, Tuple, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict


# Validation constants
MAX_ID_LENGTH = 256
MAX_METADATA_SIZE_BYTES = 10240  # 10KB max metadata size
MAX_METADATA_KEYS = 50
ID_PATTERN = r'^[a-zA-Z0-9_\-\.@]+$'

# Pagination constants
DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 1000

# Reserved metadata keys that cannot be used
RESERVED_METADATA_KEYS = {'user_id_hash', 'timestamp', 'session_id'}


def _validate_metadata_constraints(v: Optional[Dict]) -> Optional[Dict]:
    """
    Shared logic for metadata validation to avoid DRY violation.

    Args:
        v: Metadata dictionary to validate

    Returns:
        Validated metadata dictionary

    Raises:
        ValueError: If validation fails
    """
    if v is None:
        return v

    # Check number of keys
    if len(v) > MAX_METADATA_KEYS:
        raise ValueError(f"metadata exceeds maximum of {MAX_METADATA_KEYS} keys")

    # Check for reserved keys
    reserved_found = set(v.keys()) & RESERVED_METADATA_KEYS
    if reserved_found:
        raise ValueError(f"metadata contains reserved keys: {reserved_found}")

    # Check total size
    try:
        metadata_json = json.dumps(v)
        if len(metadata_json.encode('utf-8')) > MAX_METADATA_SIZE_BYTES:
            raise ValueError(
                f"metadata exceeds maximum size of {MAX_METADATA_SIZE_BYTES} bytes"
            )
    except (TypeError, ValueError) as e:
        if "exceeds maximum size" in str(e):
            raise
        raise ValueError(f"metadata is not JSON serializable: {e}")

    return v


class UserIdModel(BaseModel):
    """Pydantic model for validating user IDs."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=MAX_ID_LENGTH,
        pattern=ID_PATTERN,
        description="User identifier (alphanumeric, underscore, hyphen, dot, @)"
    )


class SessionIdModel(BaseModel):
    """Pydantic model for validating session IDs."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    session_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=MAX_ID_LENGTH,
        pattern=ID_PATTERN,
        description="Optional session identifier"
    )


class MetadataModel(BaseModel):
    """Pydantic model for validating metadata dictionaries."""
    model_config = ConfigDict(extra='forbid')
    
    metadata: Optional[Dict[str, Union[str, int, float, bool, None]]] = Field(
        default=None,
        description="Optional metadata dictionary"
    )
    
    @field_validator('metadata')
    @classmethod
    def validate_metadata(cls, v: Optional[Dict]) -> Optional[Dict]:
        """Validate metadata size and key constraints."""
        return _validate_metadata_constraints(v)


class PaginationModel(BaseModel):
    """Pydantic model for validating and normalizing pagination parameters."""
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    offset: Optional[str] = Field(default=None, description="Cursor (Point ID) for next page")

    @field_validator('limit', mode='before')
    @classmethod
    def validate_limit(cls, v: Any) -> int:
        """Validate limit is a positive integer within valid range."""
        if not isinstance(v, int) or isinstance(v, bool):
            raise ValueError("limit must be an integer")
        if v < 1:
            raise ValueError("limit must be at least 1")
        if v > MAX_PAGE_LIMIT:
            raise ValueError(f"limit cannot exceed {MAX_PAGE_LIMIT}")
        return v


class MemoryInput(BaseModel):
    """Combined Pydantic model for memory operation inputs."""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=MAX_ID_LENGTH,
        pattern=ID_PATTERN,
        description="User identifier"
    )
    session_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=MAX_ID_LENGTH,
        pattern=ID_PATTERN,
        description="Optional session identifier"
    )
    metadata: Optional[Dict[str, Union[str, int, float, bool, None]]] = Field(
        default=None,
        description="Optional metadata dictionary"
    )
    
    @field_validator('metadata')
    @classmethod
    def validate_metadata(cls, v: Optional[Dict]) -> Optional[Dict]:
        """Validate metadata size and key constraints."""
        return _validate_metadata_constraints(v)


# Backward-compatible function wrappers
def validate_id(value: str, field_name: str) -> None:
    """
    Validate user_id or session_id format using Pydantic.
    
    Args:
        value: The ID value to validate
        field_name: Name of the field for error messages
        
    Raises:
        ValueError: If validation fails
    """
    from pydantic import ValidationError
    
    try:
        if field_name == "session_id":
            SessionIdModel(session_id=value)
        else:
            UserIdModel(user_id=value)
    except ValidationError as e:
        # Extract first error message for backward compatibility
        error = e.errors()[0]
        error_type = error.get('type', '')
        
        if error_type == 'string_too_long':
            raise ValueError(f"{field_name} exceeds maximum length of {MAX_ID_LENGTH}")
        elif error_type == 'string_pattern_mismatch':
            raise ValueError(
                f"{field_name} contains invalid characters. "
                "Allowed: alphanumeric, underscore, hyphen, dot, @"
            )
        elif error_type in ('string_too_short', 'missing'):
            raise ValueError(f"{field_name} must be a non-empty string")
        else:
            raise ValueError(f"{field_name} validation failed: {error.get('msg', str(e))}")


def validate_metadata(metadata: Optional[Dict[str, Any]]) -> None:
    """
    Validate metadata is JSON serializable and within limits using Pydantic.
    
    Args:
        metadata: The metadata dictionary to validate
        
    Raises:
        ValueError: If validation fails
    """
    from pydantic import ValidationError
    
    try:
        MetadataModel(metadata=metadata)
    except ValidationError as e:
        # Extract first error message for backward compatibility
        error = e.errors()[0]
        msg = error.get('msg', str(e))
        raise ValueError(msg)


def validate_pagination(limit: int, offset: Optional[str] = None) -> Tuple[int, Optional[str]]:
    """
    Validate and normalize pagination parameters using Pydantic.
    
    Args:
        limit: Requested page size
        offset: Cursor for pagination (point ID from previous page's next_page_offset)
        
    Returns:
        Tuple of (normalized_limit, normalized_offset)
    """
    pagination = PaginationModel(limit=limit, offset=offset)
    return pagination.limit, pagination.offset
