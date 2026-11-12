"""
Shared cryptographic utilities.

Kept outside the api layer so services can hash API keys
without creating a circular import through api.dependencies.
"""

import hashlib
import secrets


def hash_api_key(api_key: str) -> str:
    """Hash the API key using SHA-256 for secure lookup."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a cryptographically secure random API key."""
    return secrets.token_urlsafe(32)
