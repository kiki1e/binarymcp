import hashlib


def hash_key(raw_key: str) -> str:
    """SHA256 hash for deduplication."""
    return hashlib.sha256(raw_key.encode()).hexdigest()
