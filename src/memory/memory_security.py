import hashlib
from loguru import logger

from ..config import get_settings


class MemorySecurity:
    """Security utilities for conversation memory operations."""
    
    @staticmethod
    def _get_validated_secret_key(error_message: str) -> str:
        """
        Retrieve and validate memory secret key from settings.
        
        Preference order:
        1. MEMORY_SECRET_KEY (recommended, memory-only key)
        2. SECRET_KEY (backward-compatible fallback)

        Ensures the selected secret exists and is not empty/whitespace.
        """
        settings = get_settings()
        secret = getattr(settings, 'MEMORY_SECRET_KEY', None) or getattr(settings, 'SECRET_KEY', None)
        secret_str = str(secret).strip() if secret is not None else ""
        if not secret_str:
            raise ValueError(error_message)
        return secret_str
    
    @staticmethod
    def anonymize_user_id(user_id: str) -> str:
        """
        Create a one-way hash of user_id for storage.
        
        Uses SHA-256 with a salt derived from settings to prevent rainbow table attacks.
        The hash is truncated for readability while maintaining sufficient entropy.
        
        Args:
            user_id: The raw user ID
            
        Returns:
            Anonymized user ID hash (first 32 chars of hex digest)
            
        Raises:
            ValueError: If MEMORY_SECRET_KEY/SECRET_KEY is not configured
        """
        salt = MemorySecurity._get_validated_secret_key(
            "MEMORY_SECRET_KEY (preferred) or SECRET_KEY must be configured for secure user ID anonymization. "
            "Cannot proceed without a cryptographic secret."
        )
        
        salted = f"{salt}:{user_id}".encode('utf-8')
        return hashlib.sha256(salted).hexdigest()[:32]
    
    @staticmethod
    def generate_delete_token(user_id: str) -> str:
        """
        Generate a delete authorization token for a user.
        
        This token must be provided when deleting memories to prevent
        unauthorized deletion. The token is derived from the user_id
        and a secret, making it verifiable without storing state.
        
        Args:
            user_id: The user ID to generate token for
            
        Returns:
            Authorization token (hex string)
            
        Raises:
            ValueError: If MEMORY_SECRET_KEY/SECRET_KEY is not configured
        """
        salt = MemorySecurity._get_validated_secret_key(
            "MEMORY_SECRET_KEY (preferred) or SECRET_KEY must be configured for secure delete token generation. "
            "Cannot proceed without a cryptographic secret."
        )
        
        token_input = f"{salt}:delete:{user_id}".encode('utf-8')
        return hashlib.sha256(token_input).hexdigest()[:32]
    
    @staticmethod
    def verify_delete_token(user_id: str, token: str) -> bool:
        """
        Verify a delete authorization token.

        Args:
            user_id: The user ID the token should authorize
            token: The authorization token to verify

        Returns:
            True if token is valid, False otherwise
        """
        # Ensure token is a string to prevent type errors in compare_digest
        if not isinstance(token, str):
            token = ""

        try:
            # Always generate a token to ensure constant-time execution path.
            # If user_id is invalid, generate_delete_token will raise ValueError.
            if not user_id or not isinstance(user_id, str):
                raise ValueError("Invalid user_id")
            expected = MemorySecurity.generate_delete_token(user_id)
        except ValueError:
            # In case of invalid user_id, use a non-constant dummy for timing safety.
            # If memory secret is missing, that's a critical config error - don't mask it.
            try:
                # Verify MEMORY_SECRET_KEY/SECRET_KEY exists - if not, this should fail loudly
                MemorySecurity._get_validated_secret_key("MEMORY_SECRET_KEY or SECRET_KEY required")
            except ValueError as e:
                # Missing memory secret is a critical error - log and re-raise
                logger.error(f"Critical security misconfiguration: {e}")
                raise

            # For invalid user_id only: generate a unique dummy based on the token
            # to prevent distinguishing error cases via fixed dummy comparison
            expected = hashlib.sha256(token.encode('utf-8') + b"invalid").hexdigest()[:32]
            logger.warning("verify_delete_token called with invalid user_id")

        # Use constant-time comparison to prevent timing attacks
        return hashlib.compare_digest(expected, token)
