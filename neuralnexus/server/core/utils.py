"""
core/utils.py
-------------
Shared utility functions used throughout the NeuralNexus server.
"""

import os
import hashlib
import uuid
import zipfile
from io import BytesIO
from datetime import datetime


def sha256_hash(value: str) -> str:
    """Return the SHA-256 hex digest of a string."""
    return hashlib.sha256(value.encode()).hexdigest()


def get_timestamp() -> str:
    """Return the current UTC timestamp formatted as YYYYMMDDHHmmss."""
    return datetime.now().strftime("%Y%m%d%H%M%S")


# Legacy alias used by older modules (keep for compatibility)
getTimestamp = get_timestamp


def get_uuid() -> str:
    """Generate and return a new random UUID as a string."""
    return str(uuid.uuid4())


def zip_files_in_directory(directory_path: str) -> bytes:
    """
    Compress all files in *directory_path* into an in-memory ZIP archive.

    Returns the raw bytes of the ZIP file.
    """
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_name in os.listdir(directory_path):
            file_path = os.path.join(directory_path, file_name)
            if os.path.isfile(file_path):
                zf.write(file_path, arcname=file_name)
    zip_buffer.seek(0)
    return zip_buffer.getvalue()
