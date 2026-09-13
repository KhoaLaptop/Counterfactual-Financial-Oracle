"""
Security utilities for file handling, input validation, and sanitization.
"""

import os
import re
import hashlib
import magic
from pathlib import Path
from typing import Optional, Tuple
from werkzeug.utils import secure_filename as werkzeug_secure_filename
import tempfile

from ..config import settings
from .logging import get_logger

logger = get_logger(__name__)


class SecurityError(Exception):
    """Base class for security-related errors."""
    pass


class FileValidationError(SecurityError):
    """Raised when file validation fails."""
    pass


class PathTraversalError(SecurityError):
    """Raised when path traversal is detected."""
    pass


def secure_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and injection attacks.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem operations
    """
    # Use werkzeug's secure_filename as base
    safe_name = werkzeug_secure_filename(filename)
    
    # Additional sanitization
    # Remove any remaining path components
    safe_name = os.path.basename(safe_name)
    
    # Remove any null bytes
    safe_name = safe_name.replace('\x00', '')
    
    # Ensure filename is not empty
    if not safe_name:
        return "unnamed_file"
    
    # Add random suffix to prevent overwrites (only for non-empty filenames)
    random_suffix = hashlib.md5(os.urandom(16)).hexdigest()[:8]
    name, ext = os.path.splitext(safe_name)
    safe_name = f"{name}_{random_suffix}{ext}"
    
    return safe_name


def validate_file_type(file_path: str, allowed_types: Optional[list] = None) -> bool:
    """
    Validate file type using libmagic (python-magic).
    
    Args:
        file_path: Path to file to validate
        allowed_types: List of allowed MIME types
        
    Returns:
        True if file type is valid
        
    Raises:
        FileValidationError: If file type is not allowed
    """
    if allowed_types is None:
        allowed_types = ['application/pdf', 'application/json', 'text/plain']
    
    try:
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(file_path)
        
        if file_type not in allowed_types:
            logger.warning(
                "invalid_file_type",
                file_path=file_path,
                detected_type=file_type,
                allowed_types=allowed_types
            )
            raise FileValidationError(
                f"File type '{file_type}' not allowed. Allowed types: {allowed_types}"
            )
        
        return True
        
    except Exception as e:
        if isinstance(e, FileValidationError):
            raise
        logger.error("file_type_validation_error", error=str(e))
        raise FileValidationError(f"Could not validate file type: {e}")


def validate_file_size(file_path: str, max_size_mb: Optional[int] = None) -> bool:
    """
    Validate file size is within limits.
    
    Args:
        file_path: Path to file
        max_size_mb: Maximum allowed size in MB
        
    Returns:
        True if file size is valid
        
    Raises:
        FileValidationError: If file is too large
    """
    if max_size_mb is None:
        max_size_mb = settings.max_pdf_size_mb
    
    max_size_bytes = max_size_mb * 1024 * 1024
    file_size = os.path.getsize(file_path)
    
    if file_size > max_size_bytes:
        logger.warning(
            "file_too_large",
            file_path=file_path,
            size_mb=round(file_size / (1024 * 1024), 2),
            max_size_mb=max_size_mb
        )
        raise FileValidationError(
            f"File size {round(file_size / (1024 * 1024), 2)}MB exceeds maximum "
            f"allowed size of {max_size_mb}MB"
        )
    
    return True


def create_secure_temp_file(uploaded_file, suffix: str = ".pdf") -> Tuple[str, str]:
    """
    Create a secure temporary file from an uploaded file.
    
    Args:
        uploaded_file: File-like object from upload
        suffix: File suffix
        
    Returns:
        Tuple of (temp_file_path, safe_filename)
        
    Raises:
        FileValidationError: If validation fails
    """
    # Get original filename and sanitize
    original_filename = getattr(uploaded_file, 'name', 'unnamed')
    safe_filename = secure_filename(original_filename)
    
    # Create temp directory if it doesn't exist
    temp_dir = tempfile.mkdtemp(prefix="cfo_")
    
    # Construct safe path
    temp_path = os.path.join(temp_dir, safe_filename)
    
    # Ensure no path traversal
    real_temp_dir = os.path.realpath(temp_dir)
    real_file_path = os.path.realpath(temp_path)
    
    if not real_file_path.startswith(real_temp_dir):
        logger.error("path_traversal_detected", attempted_path=temp_path)
        raise PathTraversalError("Path traversal attack detected")
    
    # Write file
    try:
        with open(temp_path, 'wb') as f:
            if hasattr(uploaded_file, 'getbuffer'):
                f.write(uploaded_file.getbuffer())
            else:
                f.write(uploaded_file.read())
        
        # Validate file
        validate_file_size(temp_path)
        validate_file_type(temp_path)
        
        logger.info(
            "secure_temp_file_created",
            original_name=original_filename,
            safe_name=safe_filename,
            size_bytes=os.path.getsize(temp_path)
        )
        
        return Path(temp_path), safe_filename
        
    except Exception as e:
        # Clean up on error
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize text input to prevent injection attacks.
    
    Args:
        text: Input text
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    if not isinstance(text, str):
        text = str(text)
    
    # Remove control characters except newlines and tabs
    text = ''.join(char for char in text if char == '\n' or char == '\t' or char >= ' ')
    
    # Remove potential script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)
    
    # Trim whitespace
    text = text.strip()
    
    # Enforce max length
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text


def hash_file(file_path: str, algorithm: str = "sha256") -> str:
    """
    Calculate file hash for deduplication and integrity checking.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm to use
        
    Returns:
        Hex digest of file hash
    """
    hasher = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def cleanup_temp_file(file_path: str) -> None:
    """
    Securely delete a temporary file.
    
    Args:
        file_path: Path to file to delete
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug("temp_file_cleaned", path=file_path)
            
            # Try to remove parent directory if empty
            parent_dir = os.path.dirname(file_path)
            if os.path.exists(parent_dir) and not os.listdir(parent_dir):
                os.rmdir(parent_dir)
    except Exception as e:
        logger.warning("temp_file_cleanup_failed", path=file_path, error=str(e))
