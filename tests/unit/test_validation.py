import pytest
from datetime import datetime

from src.utils.validation import (
    URLValidator, BookmarkDataValidator, LLMResponseValidator,
    validate_url, validate_bookmark_data, validate_json_structure,
    ValidationResult, ValidationError
)


class TestURLValidator:
    """Test URL validation functionality."""
    
    def setup_method(self):
        self.validator = URLValidator()
    
    @pytest.mark.unit
    def test_valid_https_url(self):
        """Test validation of valid HTTPS URL."""
        result = self.validator.validate("https://example.com/path")
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert result.metadata['is_secure'] is True
        assert result.metadata['parsed_url']['scheme'] == 'https'
    
    @pytest.mark.unit
    def test_valid_http_url(self):
        """Test validation of valid HTTP URL."""
        result = self.validator.validate("http://example.com")
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert result.metadata['is_secure'] is False
    
    @pytest.mark.unit
    def test_invalid_scheme(self):
        """Test validation of invalid URL scheme."""
        result = self.validator.validate("ftp://example.com")
        
        assert not result.is_valid
        assert any("Invalid URL scheme" in error for error in result.errors)
    
    @pytest.mark.unit
    def test_missing_scheme(self):
        """Test validation of URL without scheme."""
        result = self.validator.validate("example.com")
        
        assert not result.is_valid
        assert any("missing scheme" in error for error in result.errors)
    
    @pytest.mark.unit
    def test_missing_domain(self):
        """Test validation of URL without domain."""
        result = self.validator.validate("https://")
        
        assert not result.is_valid
        assert any("missing domain" in error for error in result.errors)
    
    @pytest.mark.unit
    def test_localhost_warning(self):
        """Test that localhost URLs generate warnings."""
        result = self.validator.validate("http://localhost:8080/test")
        
        assert result.is_valid  # Still valid, but should have warning
        assert len(result.warnings) > 0
        assert any("local/blocked domain" in warning for warning in result.warnings)
    
    @pytest.mark.unit
    def test_empty_url(self):
        """Test validation of empty URL."""
        result = self.validator.validate("")
        
        assert not result.is_valid
        assert any("non-empty string" in error for error in result.errors)
    
    @pytest.mark.unit
    def test_none_url(self):
        """Test validation of None URL."""
        result = self.validator.validate(None)
        
        assert not result.is_valid
        assert any("non-empty string" in error for error in result.errors)
    
    @pytest.mark.unit
    def test_very_long_url(self):
        """Test validation of very long URL."""
        long_url = "https://example.com/" + "a" * 2000
        result = self.validator.validate(long_url)
        
        assert result.is_valid  # Still valid
        assert len(result.warnings) > 0
        assert any("very long" in warning for warning in result.warnings)
    
    @pytest.mark.unit
    def test_suspicious_patterns(self):
        """Test detection of suspicious URL patterns."""
        suspicious_urls = [
            "https://example.com/file.exe",
            "javascript:alert('test')",
            "https://test.onion/path"
        ]
        
        for url in suspicious_urls:
            result = self.validator.validate(url)
            # Some might be invalid due to scheme, others might just have warnings
            if result.is_valid:
                assert len(result.warnings) > 0


class TestBookmarkDataValidator:
    """Test bookmark data validation."""
    
    def setup_method(self):
        self.validator = BookmarkDataValidator()
    
    @pytest.mark.unit
    def test_valid_bookmark_data(self, sample_bookmark_data):
        """Test validation of valid bookmark data."""
        result = self.validator.validate(sample_bookmark_data)
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert result.metadata['has_content'] is True
        assert result.metadata['has_author'] is True
    
    @pytest.mark.unit
    def test_missing_required_fields(self):
        """Test validation with missing required fields."""
        invalid_data = {"url": "https://example.com"}  # Missing id and title
        
        result = self.validator.validate(invalid_data)
        
        assert not result.is_valid
        assert len(result.errors) >= 2  # At least missing id and title
        assert any("Missing required field: id" in error for error in result.errors)
        assert any("Missing required field: title" in error for error in result.errors)
    
    @pytest.mark.unit
    def test_empty_required_fields(self):
        """Test validation with empty required fields."""
        invalid_data = {
            "id": "",
            "url": "",
            "title": ""
        }
        
        result = self.validator.validate(invalid_data)
        
        assert not result.is_valid
        assert len(result.errors) >= 3
    
    @pytest.mark.unit
    def test_invalid_url_in_bookmark(self):
        """Test validation with invalid URL."""
        invalid_data = {
            "id": "test",
            "url": "invalid-url",
            "title": "Test"
        }
        
        result = self.validator.validate(invalid_data)
        
        assert not result.is_valid
        assert any("URL validation" in error for error in result.errors)
    
    @pytest.mark.unit
    def test_invalid_date_format(self):
        """Test validation with invalid date format."""
        invalid_data = {
            "id": "test",
            "url": "https://example.com",
            "title": "Test",
            "created_at": "invalid-date"
        }
        
        result = self.validator.validate(invalid_data)
        
        assert not result.is_valid
        assert any("Invalid created_at date format" in error for error in result.errors)
    
    @pytest.mark.unit
    def test_very_long_content(self):
        """Test validation with very long content."""
        data = {
            "id": "test",
            "url": "https://example.com",
            "title": "Test",
            "content": "A" * 60000  # Very long content
        }
        
        result = self.validator.validate(data)
        
        assert result.is_valid  # Still valid
        assert len(result.warnings) > 0
        assert any("very long" in warning for warning in result.warnings)
    
    @pytest.mark.unit
    def test_non_dict_input(self):
        """Test validation with non-dictionary input."""
        result = self.validator.validate("not a dict")
        
        assert not result.is_valid
        assert any("must be a dictionary" in error for error in result.errors)
    
    @pytest.mark.unit
    def test_unknown_fields_warning(self):
        """Test that unknown fields generate warnings."""
        data = {
            "id": "test",
            "url": "https://example.com",
            "title": "Test",
            "unknown_field": "value"
        }
        
        result = self.validator.validate(data)
        
        assert result.is_valid
        assert len(result.warnings) > 0
        assert any("Unknown fields" in warning for warning in result.warnings)


class TestLLMResponseValidator:
    """Test LLM response validation."""
    
    def setup_method(self):
        self.validator = LLMResponseValidator()
    
    @pytest.mark.unit
    def test_valid_llm_response(self, sample_llm_response):
        """Test validation of valid LLM response."""
        result = self.validator.validate(sample_llm_response)
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert 'content_length' in result.metadata
        assert 'word_count' in result.metadata
    
    @pytest.mark.unit
    def test_missing_required_fields(self):
        """Test validation with missing required fields."""
        invalid_response = {"content": "test"}  # Missing usage and model
        
        result = self.validator.validate(invalid_response)
        
        assert not result.is_valid
        assert any("Missing required field: usage" in error for error in result.errors)
        assert any("Missing required field: model" in error for error in result.errors)
    
    @pytest.mark.unit
    def test_empty_content(self):
        """Test validation with empty content."""
        invalid_response = {
            "content": "",
            "usage": {"total_tokens": 0},
            "model": "test"
        }
        
        result = self.validator.validate(invalid_response)
        
        assert not result.is_valid
        assert any("Content is empty" in error for error in result.errors)
    
    @pytest.mark.unit
    def test_invalid_usage_format(self):
        """Test validation with invalid usage format."""
        invalid_response = {
            "content": "test",
            "usage": "not a dict",
            "model": "test"
        }
        
        result = self.validator.validate(invalid_response)
        
        assert not result.is_valid
        assert any("Usage must be a dictionary" in error for error in result.errors)
    
    @pytest.mark.unit
    def test_negative_token_counts(self):
        """Test validation with negative token counts."""
        invalid_response = {
            "content": "test",
            "usage": {"total_tokens": -10},
            "model": "test"
        }
        
        result = self.validator.validate(invalid_response)
        
        assert not result.is_valid
        assert any("non-negative integer" in error for error in result.errors)
    
    @pytest.mark.unit
    def test_high_processing_time_warning(self):
        """Test that high processing time generates warning."""
        response = {
            "content": "test",
            "usage": {"total_tokens": 10},
            "model": "test",
            "processing_time": 400  # Over 5 minutes
        }
        
        result = self.validator.validate(response)
        
        assert result.is_valid
        assert len(result.warnings) > 0
        assert any("very high" in warning for warning in result.warnings)


class TestConvenienceFunctions:
    """Test convenience validation functions."""
    
    @pytest.mark.unit
    def test_validate_url_function(self):
        """Test validate_url convenience function."""
        assert validate_url("https://example.com") is True
        assert validate_url("invalid-url") is False
        assert validate_url("") is False
    
    @pytest.mark.unit
    def test_validate_bookmark_data_function(self, sample_bookmark_data):
        """Test validate_bookmark_data convenience function."""
        assert validate_bookmark_data(sample_bookmark_data) is True
        assert validate_bookmark_data({}) is False
        assert validate_bookmark_data("not a dict") is False
    
    @pytest.mark.unit
    def test_validate_json_structure(self):
        """Test JSON structure validation."""
        data = {"field1": "value1", "field2": "value2"}
        required_fields = ["field1", "field2"]
        
        result = validate_json_structure(data, required_fields)
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert result.metadata['field_count'] == 2
    
    @pytest.mark.unit
    def test_validate_json_structure_missing_fields(self):
        """Test JSON structure validation with missing fields."""
        data = {"field1": "value1"}
        required_fields = ["field1", "field2", "field3"]
        
        result = validate_json_structure(data, required_fields)
        
        assert not result.is_valid
        assert any("Missing required fields" in error for error in result.errors)


class TestValidationResult:
    """Test ValidationResult class."""
    
    @pytest.mark.unit
    def test_validation_result_creation(self):
        """Test ValidationResult creation."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=["test warning"],
            metadata={"test": "data"}
        )
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert result.metadata["test"] == "data"
    
    @pytest.mark.unit
    def test_validation_result_with_errors(self):
        """Test ValidationResult with errors."""
        result = ValidationResult(
            is_valid=False,
            errors=["error1", "error2"],
            warnings=[],
            metadata={}
        )
        
        assert result.is_valid is False
        assert len(result.errors) == 2
        assert "error1" in result.errors
        assert "error2" in result.errors


class TestValidationError:
    """Test ValidationError exception."""
    
    @pytest.mark.unit
    def test_validation_error_creation(self):
        """Test ValidationError creation."""
        errors = ["error1", "error2"]
        exception = ValidationError("Test validation failed", errors)
        
        assert str(exception) == "Test validation failed"
        assert exception.errors == errors
    
    @pytest.mark.unit
    def test_validation_error_without_errors(self):
        """Test ValidationError without specific errors."""
        exception = ValidationError("Test validation failed")
        
        assert str(exception) == "Test validation failed"
        assert exception.errors == []