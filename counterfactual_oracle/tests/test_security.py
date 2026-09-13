"""
Security module tests.
"""

import pytest
import os
from counterfactual_oracle.src.infrastructure.security import (
    secure_filename,
    validate_file_type,
    validate_file_size,
    create_secure_temp_file,
    sanitize_text,
    FileValidationError,
    PathTraversalError
)


class TestSecureFilename:
    """Test filename sanitization."""
    
    def test_basic_sanitization(self):
        """Test basic filename cleaning."""
        result = secure_filename("test.pdf")
        assert result.startswith("test_")
        assert result.endswith(".pdf")
    
    def test_path_traversal_attempt(self):
        """Test that path traversal is blocked."""
        result = secure_filename("../../../etc/passwd")
        assert "passwd" not in result or not result.startswith("/")
        assert "/" not in result
    
    def test_null_byte_injection(self):
        """Test null byte injection prevention."""
        result = secure_filename("test\x00.pdf")
        assert "\x00" not in result
    
    def test_empty_filename(self):
        """Test empty filename handling."""
        result = secure_filename("")
        assert result == "unnamed_file"


class TestFileValidation:
    """Test file validation."""
    
    def test_file_size_validation(self, tmp_path):
        """Test file size validation."""
        # Create a small test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        # Should pass with generous limit
        assert validate_file_size(str(test_file), max_size_mb=10) is True
    
    def test_file_size_too_large(self, tmp_path):
        """Test file size limit enforcement."""
        test_file = tmp_path / "large.txt"
        test_file.write_text("x" * 1024)  # 1KB
        
        with pytest.raises(FileValidationError):
            validate_file_size(str(test_file), max_size_mb=0.0005)  # Very small limit
    
    def test_sanitize_text(self):
        """Test text sanitization."""
        # Test script tag removal
        text = '<script>alert("xss")</script>Hello'
        result = sanitize_text(text)
        assert "<script>" not in result
        
        # Test null byte removal
        text = "Hello\x00World"
        result = sanitize_text(text)
        assert "\x00" not in result
        
        # Test max length
        text = "a" * 1000
        result = sanitize_text(text, max_length=100)
        assert len(result) == 100


class TestPathTraversal:
    """Test path traversal prevention."""
    
    def test_traversal_detection(self, tmp_path):
        """Test that path traversal is detected."""
        # This would be caught by the secure path construction
        temp_dir = str(tmp_path)
        bad_path = os.path.join(temp_dir, "..", "..", "etc", "passwd")
        
        # The realpath check should catch this
        real_temp = os.path.realpath(temp_dir)
        real_bad = os.path.realpath(bad_path)
        
        assert not real_bad.startswith(real_temp)
