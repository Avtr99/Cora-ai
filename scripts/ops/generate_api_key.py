#!/usr/bin/env python3
"""
Generate a secure API key for client authentication.

This script generates a cryptographically secure API key that can be used
to authenticate requests to the Cora API.

Usage:
    python scripts/ops/generate_api_key.py

The generated key should be:
1. Added to your .env file as API_ACCESS_KEY
2. Shared with anyone who needs API access (via a secure channel)
3. Never committed to git (the .env file is gitignored)
"""

import secrets


def generate_api_key() -> str:
    """
    Generate a secure API key for client authentication.

    Returns:
        A 64-character hexadecimal API key (32 bytes)
    """
    return secrets.token_hex(32)


def main():
    """Generate and display API key with setup instructions."""
    api_key = generate_api_key()

    print("=" * 70)
    print("API Key Generated")
    print("=" * 70)
    print()
    print(f"Your API Key: {api_key}")
    print()
    print("=" * 70)
    print("Setup Instructions")
    print("=" * 70)
    print()
    print("1. Add to your local .env file:")
    print(f"   API_ACCESS_KEY={api_key}")
    print()
    print("2. Share this key with anyone who needs API access via a secure channel.")
    print()
    print("3. If you deploy Cora publicly, set the key in the server environment")
    print("   (e.g. via your hosting platform's secrets/env vars). Never commit it.")
    print()
    print("4. Update frontend/.env.local:")
    print("   VITE_API_KEY=<your-api-key>")
    print()
    print("=" * 70)
    print("Security Notes")
    print("=" * 70)
    print()
    print("- Never commit API keys to git")
    print("- Rotate API keys regularly (recommended: every 90 days)")
    print("- Use different keys for development and production")
    print("- Monitor usage logs for unauthorized access")
    print("- Revoke compromised keys immediately")
    print()


if __name__ == "__main__":
    main()
