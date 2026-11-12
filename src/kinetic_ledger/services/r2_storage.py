"""
Cloudflare R2 object storage integration for Kinetic Ledger.

R2 is S3-compatible, so we use the boto3 S3 client pointed at the
Cloudflare R2 endpoint. Used in Cloud Run deployments where the local
filesystem is ephemeral.

Expected environment variables (canonical names, with the legacy
CLOUDFLARE_* names also supported):

    R2_ENDPOINT_URL      (or CLOUDFLARE_URL)      e.g. https://<account_id>.r2.cloudflarestorage.com
    R2_ACCESS_KEY_ID     (or CLOUDFLARE_KEY_ID)   S3 access key id
    R2_SECRET_ACCESS_KEY (or SECRET_ACCESS_KEY)    S3 secret access key
    R2_BUCKET_NAME       (or BUCKET_NAME)          bucket name
    R2_PUBLIC_URL        (or CLOUDFLARE_MEDIA_URL) optional public base URL for objects
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default bucket name - can be overridden via environment variable
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME") or os.getenv("BUCKET_NAME", "movimento")

# Cloudflare R2 endpoint (account-specific URL)
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL") or os.getenv("CLOUDFLARE_URL", "")

# Credentials (S3-compatible key/secret)
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID") or os.getenv("CLOUDFLARE_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("SECRET_ACCESS_KEY", "")

# Optional public base URL for stored objects
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL") or os.getenv("CLOUDFLARE_MEDIA_URL", "")

# Lazy initialization of the R2 (S3) client
_r2_client = None


def _build_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    import boto3
    from botocore.config import Config

    kwargs: Dict[str, Any] = {
        "service_name": "s3",
        "region_name": "auto",  # R2 requires region "auto"
        "config": Config(signature_version="s3v4"),  # R2 requires SigV4
    }
    if R2_ENDPOINT_URL:
        kwargs["endpoint_url"] = R2_ENDPOINT_URL
    if R2_ACCESS_KEY_ID:
        kwargs["aws_access_key_id"] = R2_ACCESS_KEY_ID
    if R2_SECRET_ACCESS_KEY:
        kwargs["aws_secret_access_key"] = R2_SECRET_ACCESS_KEY

    return boto3.client(**kwargs)


def get_r2_client():
    """Get or create the R2 (S3) client."""
    global _r2_client
    if _r2_client is None:
        try:
            _r2_client = _build_client()
            logger.info(f"R2 client initialized for bucket: {R2_BUCKET_NAME}")
        except Exception as e:
            logger.warning(f"Failed to initialize R2 client: {e}")
            return None
    return _r2_client


def reset_r2_client() -> None:
    """Reset the cached R2 client (useful for testing)."""
    global _r2_client
    _r2_client = None


def is_configured() -> bool:
    """Return True if R2 credentials are present in the environment."""
    return bool(R2_ENDPOINT_URL and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY)


def public_url(object_key: str) -> Optional[str]:
    """Build a public URL for an object if R2_PUBLIC_URL is configured."""
    if not R2_PUBLIC_URL:
        return None
    return f"{R2_PUBLIC_URL.rstrip('/')}/{object_key.lstrip('/')}"


def upload_file(local_path: str, object_key: str) -> bool:
    """
    Upload a local file to R2.

    Args:
        local_path: Path to the local file
        object_key: Destination key in R2 (e.g., 'data/mixamo_anims/file.fbx')

    Returns:
        True if successful, False otherwise
    """
    client = get_r2_client()
    if client is None:
        logger.warning("R2 client not available, skipping upload")
        return False

    try:
        client.upload_file(local_path, R2_BUCKET_NAME, object_key)
        logger.info(f"Uploaded {local_path} to r2://{R2_BUCKET_NAME}/{object_key}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload {local_path} to R2: {e}")
        return False


def download_file(object_key: str, local_path: str) -> bool:
    """
    Download a file from R2 to the local filesystem.

    Args:
        object_key: Key in R2 (e.g., 'data/mixamo_anims/file.fbx')
        local_path: Destination path on the local filesystem

    Returns:
        True if successful, False otherwise
    """
    client = get_r2_client()
    if client is None:
        logger.warning("R2 client not available, skipping download")
        return False

    try:
        # Ensure local directory exists
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        client.download_file(R2_BUCKET_NAME, object_key, local_path)
        logger.info(f"Downloaded r2://{R2_BUCKET_NAME}/{object_key} to {local_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to download {object_key} from R2: {e}")
        return False


def list_files(prefix: str = "") -> List[str]:
    """
    List object keys in the R2 bucket with an optional prefix.

    Args:
        prefix: Optional prefix to filter keys (e.g., 'data/', 'artifacts/')

    Returns:
        List of object keys in the bucket
    """
    client = get_r2_client()
    if client is None:
        return []

    try:
        paginator = client.get_paginator("list_objects_v2")
        keys: List[str] = []
        for page in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj.get("Key")
                if key:
                    keys.append(key)
        return keys
    except Exception as e:
        logger.error(f"Failed to list files with prefix {prefix}: {e}")
        return []


def upload_json(data: Dict[Any, Any], object_key: str) -> bool:
    """
    Upload JSON data directly to R2.

    Args:
        data: Dictionary to serialize as JSON
        object_key: Destination key in R2

    Returns:
        True if successful, False otherwise
    """
    client = get_r2_client()
    if client is None:
        logger.warning("R2 client not available, skipping upload")
        return False

    try:
        client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=object_key,
            Body=json.dumps(data, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        logger.info(f"Uploaded JSON to r2://{R2_BUCKET_NAME}/{object_key}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload JSON to R2: {e}")
        return False

def upload_bytes(
    content: bytes,
    object_key: str,
    content_type: Optional[str] = None,
) -> bool:
    """
    Upload raw bytes directly to Cloudflare R2.

    Args:
        content: File bytes.
        object_key: Destination object key.
        content_type: Optional MIME type.

    Returns:
        True if upload succeeds, False otherwise.
    """
    client = get_r2_client()

    if client is None:
        logger.error("R2 client is not configured")
        return False

    try:
        extra_args = {}

        if content_type:
            extra_args["ContentType"] = content_type

        client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=object_key,
            Body=content,
            **extra_args,
        )

        logger.info(
            "Uploaded bytes to R2",
            extra={
                "bucket": R2_BUCKET_NAME,
                "object_key": object_key,
                "size_bytes": len(content),
            },
        )

        return True

    except Exception as e:
        logger.error(
            "Failed to upload bytes to R2",
            extra={
                "bucket": R2_BUCKET_NAME,
                "object_key": object_key,
                "error": str(e),
            },
            exc_info=True,
        )

        return False

def download_json(object_key: str) -> Optional[Dict[Any, Any]]:
    """
    Download and parse JSON data from R2.

    Args:
        object_key: Key in R2

    Returns:
        Parsed JSON data or None if failed
    """
    client = get_r2_client()
    if client is None:
        return None

    try:
        response = client.get_object(Bucket=R2_BUCKET_NAME, Key=object_key)
        content = response["Body"].read()
        return json.loads(content)
    except Exception as e:
        logger.error(f"Failed to download JSON from {object_key}: {e}")
        return None


def file_exists(object_key: str) -> bool:
    """Check if an object exists in R2."""
    client = get_r2_client()
    if client is None:
        return False

    try:
        client.head_object(Bucket=R2_BUCKET_NAME, Key=object_key)
        return True
    except Exception as e:
        # botocore raises ClientError with 404 for missing objects
        logger.debug(f"Object {object_key} not found in R2: {e}")
        return False


def sync_directory_to_r2(local_dir: str, prefix: str) -> int:
    """
    Upload all files from a local directory to R2.

    Args:
        local_dir: Local directory path
        prefix: R2 key prefix (e.g., 'artifacts/')

    Returns:
        Number of files uploaded
    """
    local_path = Path(local_dir)
    if not local_path.exists():
        logger.warning(f"Local directory {local_dir} does not exist")
        return 0

    uploaded = 0
    for file_path in local_path.rglob("*"):
        if file_path.is_file():
            relative_path = file_path.relative_to(local_path)
            object_key = f"{prefix.rstrip('/')}/{relative_path}"
            if upload_file(str(file_path), object_key):
                uploaded += 1

    logger.info(f"Synced {uploaded} files from {local_dir} to r2://{R2_BUCKET_NAME}/{prefix}")
    return uploaded


def sync_directory_from_r2(prefix: str, local_dir: str) -> int:
    """
    Download all objects with a key prefix to a local directory.

    Args:
        prefix: R2 key prefix (e.g., 'data/')
        local_dir: Local directory path

    Returns:
        Number of files downloaded
    """
    files = list_files(prefix)
    downloaded = 0

    for object_key in files:
        if object_key.endswith("/"):
            continue  # Skip directory placeholders

        relative_path = object_key[len(prefix):].lstrip("/")
        local_path = Path(local_dir) / relative_path

        if download_file(object_key, str(local_path)):
            downloaded += 1

    logger.info(f"Synced {downloaded} files from r2://{R2_BUCKET_NAME}/{prefix} to {local_dir}")
    return downloaded


# Artifact-specific helpers


def save_blend_artifact(blend_id: str, artifact_data: Dict[Any, Any]) -> bool:
    """Save a blend artifact to R2."""
    object_key = f"artifacts/{blend_id}/metadata.json"
    return upload_json(artifact_data, object_key)


def load_blend_artifact(blend_id: str) -> Optional[Dict[Any, Any]]:
    """Load a blend artifact from R2."""
    object_key = f"artifacts/{blend_id}/metadata.json"
    return download_json(object_key)


def list_blend_artifacts() -> List[str]:
    """List all blend artifact IDs in R2."""
    files = list_files("artifacts/")
    # Extract unique blend IDs from paths like "artifacts/blend-xxx/..."
    blend_ids = set()
    for f in files:
        parts = f.split("/")
        if len(parts) >= 2 and parts[0] == "artifacts":
            blend_ids.add(parts[1])
    return sorted(list(blend_ids))
