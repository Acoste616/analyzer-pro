"""Validation utilities for bookmark data and content."""

import re
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

import validators
from pydantic import BaseModel, Field, validator

from .logger import get_logger

logger = get_logger(__name__)


class BookmarkData(BaseModel):
    """Validated bookmark data structure."""
    
    id: str
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    created_at: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator("url")
    def validate_url(cls, v):
        """Validate URL format."""
        if not validators.url(v):
            raise ValueError(f"Invalid URL: {v}")
        return v
    
    @validator("content")
    def clean_content(cls, v):
        """Clean and validate content."""
        if v:
            # Remove excessive whitespace
            v = re.sub(r'\s+', ' ', v).strip()
            # Remove null bytes
            v = v.replace('\x00', '')
        return v


class ContentQuality:
    """Content quality assessment."""
    
    def __init__(self, content: str):
        self.content = content
        self.word_count = len(content.split()) if content else 0
        self.char_count = len(content) if content else 0
        self.has_links = bool(re.search(r'https?://\S+', content)) if content else False
        self.language = self._detect_language()
        
    def _detect_language(self) -> str:
        """Simple language detection based on character patterns."""
        if not self.content:
            return "unknown"
            
        # Check for Polish characters
        polish_chars = set('ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')
        if any(char in polish_chars for char in self.content):
            return "pl"
            
        # Default to English
        return "en"
    
    @property
    def is_valid(self) -> bool:
        """Check if content meets minimum quality standards."""
        return self.word_count >= 10
    
    @property
    def quality_score(self) -> float:
        """Calculate quality score (0-1)."""
        if self.word_count == 0:
            return 0.0
            
        score = 0.0
        
        # Word count score (up to 0.4)
        if self.word_count >= 50:
            score += 0.4
        else:
            score += (self.word_count / 50) * 0.4
            
        # Has links (0.2)
        if self.has_links:
            score += 0.2
            
        # Language detected (0.2)
        if self.language != "unknown":
            score += 0.2
            
        # Reasonable length (0.2)
        if 50 <= self.word_count <= 5000:
            score += 0.2
        elif self.word_count < 50:
            score += (self.word_count / 50) * 0.2
        else:  # Too long
            score += 0.1
            
        return min(score, 1.0)


def validate_bookmark_data(data: Dict[str, Any]) -> Optional[BookmarkData]:
    """
    Validate and clean bookmark data.
    
    Args:
        data: Raw bookmark data
        
    Returns:
        Validated BookmarkData or None if invalid
    """
    try:
        # Ensure required fields
        if "id" not in data or "url" not in data:
            logger.warning("Missing required fields in bookmark data")
            return None
            
        # Clean URL
        url = data.get("url", "").strip()
        if not url:
            return None
            
        # Expand t.co links if needed
        if "t.co" in url:
            # This would be expanded by the extractor
            pass
            
        bookmark = BookmarkData(**data)
        return bookmark
        
    except Exception as e:
        logger.error(f"Failed to validate bookmark data: {e}")
        return None


def validate_content(content: str, min_quality: float = 0.3) -> bool:
    """
    Validate content quality.
    
    Args:
        content: Content to validate
        min_quality: Minimum quality score (0-1)
        
    Returns:
        True if content is valid
    """
    quality = ContentQuality(content)
    
    if not quality.is_valid:
        logger.debug("Content failed basic validation")
        return False
        
    if quality.quality_score < min_quality:
        logger.debug(f"Content quality too low: {quality.quality_score:.2f}")
        return False
        
    return True


def is_spam_content(content: str) -> bool:
    """
    Check if content appears to be spam.
    
    Args:
        content: Content to check
        
    Returns:
        True if content appears to be spam
    """
    if not content:
        return False
        
    spam_patterns = [
        r'(?i)click here now',
        r'(?i)limited time offer',
        r'(?i)act now',
        r'(?i)100% free',
        r'(?i)winner.*selected',
        r'(?i)congratulations.*won',
        r'(?i)viagra|cialis',
        r'(?i)casino|betting',
        r'(?i)earn.*\$\d+.*day',
        r'(?i)work from home.*\$\d+',
    ]
    
    for pattern in spam_patterns:
        if re.search(pattern, content):
            return True
            
    # Check for excessive caps
    if len(content) > 20:
        caps_ratio = sum(1 for c in content if c.isupper()) / len(content)
        if caps_ratio > 0.5:
            return True
            
    # Check for excessive punctuation
    punct_count = sum(1 for c in content if c in '!?')
    if punct_count > 10:
        return True
        
    return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe file system usage.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
        
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Default if empty
    if not filename:
        filename = "unnamed"
        
    return filename


def validate_export_format(format_name: str) -> bool:
    """
    Validate export format name.
    
    Args:
        format_name: Export format to validate
        
    Returns:
        True if format is supported
    """
    supported_formats = ["json", "anki", "notion", "obsidian", "csv", "markdown"]
    return format_name.lower() in supported_formats


def validate_category(category: str, allowed_categories: List[str]) -> bool:
    """
    Validate category name.
    
    Args:
        category: Category to validate
        allowed_categories: List of allowed categories
        
    Returns:
        True if category is valid
    """
    # Normalize category
    category = category.lower().strip()
    
    # Check against allowed list
    return category in [cat.lower() for cat in allowed_categories]


def extract_domain(url: str) -> Optional[str]:
    """
    Extract domain from URL.
    
    Args:
        url: URL to extract from
        
    Returns:
        Domain name or None
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Remove www prefix
        if domain.startswith('www.'):
            domain = domain[4:]
            
        return domain
    except Exception:
        return None


def is_video_url(url: str) -> bool:
    """
    Check if URL points to a video.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL is a video
    """
    video_domains = [
        'youtube.com',
        'youtu.be',
        'vimeo.com',
        'twitch.tv',
        'dailymotion.com',
        'facebook.com/watch',
        'twitter.com/i/broadcasts',
        'x.com/i/broadcasts',
    ]
    
    domain = extract_domain(url)
    if not domain:
        return False
        
    return any(video_domain in domain for video_domain in video_domains)


def estimate_reading_time(content: str, words_per_minute: int = 200) -> int:
    """
    Estimate reading time in minutes.
    
    Args:
        content: Content to estimate
        words_per_minute: Reading speed
        
    Returns:
        Estimated minutes
    """
    if not content:
        return 0
        
    word_count = len(content.split())
    minutes = word_count / words_per_minute
    
    # Round up to nearest minute
    return max(1, int(minutes + 0.5))