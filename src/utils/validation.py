import re
import json
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
from urllib.parse import urlparse
from dataclasses import dataclass

from .logger import get_logger


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]


class ValidationError(Exception):
    """Custom validation error"""
    
    def __init__(self, message: str, errors: List[str] = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


class BaseValidator:
    """Base validator class"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def validate(self, data: Any) -> ValidationResult:
        """Override in subclasses"""
        raise NotImplementedError
    
    def _add_error(self, errors: List[str], message: str):
        """Add error message"""
        errors.append(message)
        self.logger.warning(f"Validation error: {message}")
    
    def _add_warning(self, warnings: List[str], message: str):
        """Add warning message"""
        warnings.append(message)
        self.logger.debug(f"Validation warning: {message}")


class URLValidator(BaseValidator):
    """URL validation"""
    
    def __init__(self):
        super().__init__()
        self.valid_schemes = {'http', 'https', 'ftp', 'ftps'}
        self.blocked_domains = {'localhost', '127.0.0.1', '0.0.0.0'}
    
    def validate(self, url: str) -> ValidationResult:
        """Validate URL format and accessibility"""
        
        errors = []
        warnings = []
        metadata = {}
        
        if not url or not isinstance(url, str):
            self._add_error(errors, "URL must be a non-empty string")
            return ValidationResult(False, errors, warnings, metadata)
        
        url = url.strip()
        
        try:
            parsed = urlparse(url)
            metadata['parsed_url'] = {
                'scheme': parsed.scheme,
                'netloc': parsed.netloc,
                'path': parsed.path,
                'params': parsed.params,
                'query': parsed.query,
                'fragment': parsed.fragment
            }
            
            # Check scheme
            if not parsed.scheme:
                self._add_error(errors, "URL missing scheme (http/https)")
            elif parsed.scheme.lower() not in self.valid_schemes:
                self._add_error(errors, f"Invalid URL scheme: {parsed.scheme}")
            
            # Check netloc (domain)
            if not parsed.netloc:
                self._add_error(errors, "URL missing domain")
            else:
                domain = parsed.netloc.lower()
                
                # Check for blocked domains
                if any(blocked in domain for blocked in self.blocked_domains):
                    self._add_warning(warnings, f"URL points to local/blocked domain: {domain}")
                
                # Check domain format
                if not self._is_valid_domain(domain):
                    self._add_error(errors, f"Invalid domain format: {domain}")
            
            # Check for suspicious patterns
            suspicious_patterns = [
                r'\.exe$', r'\.zip$', r'\.rar$', r'\.tar\.gz$',  # File downloads
                r'javascript:', r'data:', r'blob:',  # Potentially unsafe schemes
                r'\.onion$',  # Tor domains
            ]
            
            for pattern in suspicious_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    self._add_warning(warnings, f"URL contains suspicious pattern: {pattern}")
            
            # URL length check
            if len(url) > 2000:
                self._add_warning(warnings, "URL is very long (>2000 characters)")
            
            metadata['url_length'] = len(url)
            metadata['is_secure'] = parsed.scheme.lower() == 'https'
            
        except Exception as e:
            self._add_error(errors, f"URL parsing failed: {str(e)}")
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings, metadata)
    
    def _is_valid_domain(self, domain: str) -> bool:
        """Check if domain format is valid"""
        
        # Remove port if present
        domain = domain.split(':')[0]
        
        # Basic domain regex
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        
        return bool(re.match(domain_pattern, domain))


class BookmarkDataValidator(BaseValidator):
    """Bookmark data validation"""
    
    def __init__(self):
        super().__init__()
        self.required_fields = {'id', 'url', 'title'}
        self.optional_fields = {'content', 'author', 'created_at', 'metadata'}
        self.url_validator = URLValidator()
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate bookmark data structure"""
        
        errors = []
        warnings = []
        metadata = {}
        
        if not isinstance(data, dict):
            self._add_error(errors, "Bookmark data must be a dictionary")
            return ValidationResult(False, errors, warnings, metadata)
        
        # Check required fields
        for field in self.required_fields:
            if field not in data:
                self._add_error(errors, f"Missing required field: {field}")
            elif not data[field]:
                self._add_error(errors, f"Required field is empty: {field}")
        
        # Validate specific fields
        if 'id' in data:
            if not isinstance(data['id'], str) or len(data['id']) < 1:
                self._add_error(errors, "ID must be a non-empty string")
            elif len(data['id']) > 100:
                self._add_warning(warnings, "ID is very long (>100 characters)")
        
        if 'url' in data:
            url_result = self.url_validator.validate(data['url'])
            if not url_result.is_valid:
                errors.extend([f"URL validation: {error}" for error in url_result.errors])
            warnings.extend([f"URL validation: {warning}" for warning in url_result.warnings])
            metadata['url_validation'] = url_result.metadata
        
        if 'title' in data:
            title = data['title']
            if not isinstance(title, str):
                self._add_error(errors, "Title must be a string")
            elif len(title) > 500:
                self._add_warning(warnings, "Title is very long (>500 characters)")
        
        if 'content' in data and data['content']:
            content = data['content']
            if not isinstance(content, str):
                self._add_error(errors, "Content must be a string")
            else:
                metadata['content_length'] = len(content)
                if len(content) > 50000:
                    self._add_warning(warnings, "Content is very long (>50,000 characters)")
        
        if 'created_at' in data and data['created_at']:
            created_at = data['created_at']
            if isinstance(created_at, str):
                try:
                    datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except ValueError:
                    self._add_error(errors, "Invalid created_at date format")
            elif not isinstance(created_at, datetime):
                self._add_error(errors, "created_at must be a datetime or ISO string")
        
        # Check for unknown fields
        all_known_fields = self.required_fields | self.optional_fields
        unknown_fields = set(data.keys()) - all_known_fields
        if unknown_fields:
            self._add_warning(warnings, f"Unknown fields: {', '.join(unknown_fields)}")
        
        metadata['field_count'] = len(data)
        metadata['has_content'] = bool(data.get('content', '').strip())
        metadata['has_author'] = bool(data.get('author', '').strip())
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings, metadata)


class LLMResponseValidator(BaseValidator):
    """LLM response validation"""
    
    def __init__(self):
        super().__init__()
    
    def validate(self, response: Dict[str, Any]) -> ValidationResult:
        """Validate LLM response structure"""
        
        errors = []
        warnings = []
        metadata = {}
        
        if not isinstance(response, dict):
            self._add_error(errors, "LLM response must be a dictionary")
            return ValidationResult(False, errors, warnings, metadata)
        
        # Check required fields
        required_fields = {'content', 'usage', 'model'}
        for field in required_fields:
            if field not in response:
                self._add_error(errors, f"Missing required field: {field}")
        
        # Validate content
        if 'content' in response:
            content = response['content']
            if not isinstance(content, str):
                self._add_error(errors, "Content must be a string")
            elif not content.strip():
                self._add_error(errors, "Content is empty")
            else:
                metadata['content_length'] = len(content)
                metadata['word_count'] = len(content.split())
        
        # Validate usage
        if 'usage' in response:
            usage = response['usage']
            if not isinstance(usage, dict):
                self._add_error(errors, "Usage must be a dictionary")
            else:
                # Check for common usage fields
                usage_fields = ['prompt_tokens', 'completion_tokens', 'total_tokens']
                for field in usage_fields:
                    if field in usage:
                        if not isinstance(usage[field], int) or usage[field] < 0:
                            self._add_error(errors, f"Usage field {field} must be a non-negative integer")
                
                metadata['token_usage'] = usage
        
        # Validate model
        if 'model' in response:
            model = response['model']
            if not isinstance(model, str) or not model.strip():
                self._add_error(errors, "Model must be a non-empty string")
        
        # Check processing time
        if 'processing_time' in response:
            processing_time = response['processing_time']
            if not isinstance(processing_time, (int, float)) or processing_time < 0:
                self._add_error(errors, "Processing time must be a non-negative number")
            elif processing_time > 300:  # 5 minutes
                self._add_warning(warnings, "Processing time is very high (>5 minutes)")
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings, metadata)


class ConfigValidator(BaseValidator):
    """Configuration validation"""
    
    def __init__(self):
        super().__init__()
    
    def validate(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate configuration structure"""
        
        errors = []
        warnings = []
        metadata = {}
        
        if not isinstance(config, dict):
            self._add_error(errors, "Configuration must be a dictionary")
            return ValidationResult(False, errors, warnings, metadata)
        
        # Check required sections
        required_sections = ['app', 'logging', 'database', 'processing']
        for section in required_sections:
            if section not in config:
                self._add_error(errors, f"Missing required configuration section: {section}")
        
        # Validate app section
        if 'app' in config:
            app_config = config['app']
            if not isinstance(app_config, dict):
                self._add_error(errors, "App configuration must be a dictionary")
            else:
                required_app_fields = ['name', 'version', 'environment']
                for field in required_app_fields:
                    if field not in app_config:
                        self._add_error(errors, f"Missing app configuration field: {field}")
        
        # Validate logging section
        if 'logging' in config:
            logging_config = config['logging']
            if not isinstance(logging_config, dict):
                self._add_error(errors, "Logging configuration must be a dictionary")
            else:
                if 'level' in logging_config:
                    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
                    if logging_config['level'] not in valid_levels:
                        self._add_error(errors, f"Invalid logging level: {logging_config['level']}")
        
        # Validate database section
        if 'database' in config:
            db_config = config['database']
            if not isinstance(db_config, dict):
                self._add_error(errors, "Database configuration must be a dictionary")
            else:
                if 'type' in db_config:
                    valid_types = ['sqlite', 'postgresql', 'mysql']
                    if db_config['type'] not in valid_types:
                        self._add_error(errors, f"Invalid database type: {db_config['type']}")
        
        # Validate processing section
        if 'processing' in config:
            proc_config = config['processing']
            if not isinstance(proc_config, dict):
                self._add_error(errors, "Processing configuration must be a dictionary")
            else:
                numeric_fields = ['batch_size', 'max_workers', 'checkpoint_interval']
                for field in numeric_fields:
                    if field in proc_config:
                        value = proc_config[field]
                        if not isinstance(value, int) or value <= 0:
                            self._add_error(errors, f"Processing {field} must be a positive integer")
        
        metadata['section_count'] = len(config)
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings, metadata)


class DataValidator:
    """Main data validator that coordinates all validators"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.url_validator = URLValidator()
        self.bookmark_validator = BookmarkDataValidator()
        self.llm_validator = LLMResponseValidator()
        self.config_validator = ConfigValidator()
    
    def validate_url(self, url: str) -> ValidationResult:
        """Validate URL"""
        return self.url_validator.validate(url)
    
    def validate_bookmark_data(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate bookmark data"""
        return self.bookmark_validator.validate(data)
    
    def validate_llm_response(self, response: Dict[str, Any]) -> ValidationResult:
        """Validate LLM response"""
        return self.llm_validator.validate(response)
    
    def validate_config(self, config: Dict[str, Any]) -> ValidationResult:
        """Validate configuration"""
        return self.config_validator.validate(config)
    
    def validate_batch_data(self, data_list: List[Dict[str, Any]], 
                          validator_type: str = 'bookmark') -> Tuple[List[ValidationResult], Dict[str, Any]]:
        """Validate a batch of data"""
        
        results = []
        summary = {
            'total_items': len(data_list),
            'valid_items': 0,
            'invalid_items': 0,
            'items_with_warnings': 0,
            'common_errors': {},
            'common_warnings': {}
        }
        
        # Choose validator
        if validator_type == 'bookmark':
            validator = self.bookmark_validator
        elif validator_type == 'llm':
            validator = self.llm_validator
        elif validator_type == 'config':
            validator = self.config_validator
        else:
            raise ValueError(f"Unknown validator type: {validator_type}")
        
        # Validate each item
        for i, data in enumerate(data_list):
            try:
                result = validator.validate(data)
                results.append(result)
                
                if result.is_valid:
                    summary['valid_items'] += 1
                else:
                    summary['invalid_items'] += 1
                
                if result.warnings:
                    summary['items_with_warnings'] += 1
                
                # Count common errors and warnings
                for error in result.errors:
                    summary['common_errors'][error] = summary['common_errors'].get(error, 0) + 1
                
                for warning in result.warnings:
                    summary['common_warnings'][warning] = summary['common_warnings'].get(warning, 0) + 1
                    
            except Exception as e:
                self.logger.error(f"Validation failed for item {i}: {str(e)}")
                error_result = ValidationResult(
                    is_valid=False,
                    errors=[f"Validation error: {str(e)}"],
                    warnings=[],
                    metadata={}
                )
                results.append(error_result)
                summary['invalid_items'] += 1
        
        # Sort common issues by frequency
        summary['common_errors'] = dict(sorted(summary['common_errors'].items(), 
                                             key=lambda x: x[1], reverse=True)[:10])
        summary['common_warnings'] = dict(sorted(summary['common_warnings'].items(), 
                                               key=lambda x: x[1], reverse=True)[:10])
        
        return results, summary


# Convenience functions for quick validation
def validate_url(url: str) -> bool:
    """Quick URL validation (returns boolean)"""
    validator = URLValidator()
    result = validator.validate(url)
    return result.is_valid


def validate_bookmark_data(data: Dict[str, Any]) -> bool:
    """Quick bookmark data validation (returns boolean)"""
    validator = BookmarkDataValidator()
    result = validator.validate(data)
    return result.is_valid


def validate_json_structure(data: Any, required_fields: List[str] = None) -> ValidationResult:
    """Validate JSON structure with required fields"""
    
    errors = []
    warnings = []
    metadata = {}
    
    if not isinstance(data, dict):
        errors.append("Data must be a dictionary/object")
        return ValidationResult(False, errors, warnings, metadata)
    
    if required_fields:
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
        
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
    
    metadata['field_count'] = len(data)
    metadata['fields'] = list(data.keys())
    
    is_valid = len(errors) == 0
    return ValidationResult(is_valid, errors, warnings, metadata)


def validate_file_path(file_path: str, must_exist: bool = False, 
                      allowed_extensions: List[str] = None) -> ValidationResult:
    """Validate file path"""
    
    errors = []
    warnings = []
    metadata = {}
    
    if not file_path or not isinstance(file_path, str):
        errors.append("File path must be a non-empty string")
        return ValidationResult(False, errors, warnings, metadata)
    
    from pathlib import Path
    
    try:
        path = Path(file_path)
        metadata['absolute_path'] = str(path.absolute())
        metadata['exists'] = path.exists()
        metadata['is_file'] = path.is_file() if path.exists() else None
        metadata['is_dir'] = path.is_dir() if path.exists() else None
        metadata['extension'] = path.suffix.lower()
        
        if must_exist and not path.exists():
            errors.append(f"File does not exist: {file_path}")
        
        if allowed_extensions and path.suffix.lower() not in allowed_extensions:
            errors.append(f"File extension not allowed. Expected: {allowed_extensions}")
        
        if path.exists() and path.is_dir():
            warnings.append("Path points to a directory, not a file")
        
    except Exception as e:
        errors.append(f"Invalid file path: {str(e)}")
    
    is_valid = len(errors) == 0
    return ValidationResult(is_valid, errors, warnings, metadata)