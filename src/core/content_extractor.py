import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse, urljoin
import re

from ..config.settings import settings_manager
from ..utils.logger import get_logger
from ..utils.validation import validate_url


@dataclass
class ExtractedContent:
    title: str
    content: str
    author: str
    published_date: Optional[datetime]
    metadata: Dict[str, Any]
    media_urls: List[str]
    extracted_at: datetime


class BaseContentExtractor(ABC):
    def __init__(self):
        self.settings = settings_manager.settings
        self.logger = get_logger(__name__)
        self.session = None
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        timeout = aiohttp.ClientTimeout(total=self.settings.extractors.get('web_scraping', {}).get('timeout', 30))
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': self.settings.extractors.get('web_scraping', {}).get('user_agent', 'BookmarkAnalyzer/1.0')}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @abstractmethod
    async def extract(self, url: str) -> ExtractedContent:
        pass
    
    async def _fetch_content(self, url: str) -> str:
        if not validate_url(url):
            raise ValueError(f"Invalid URL: {url}")
        
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            self.logger.error(f"Error fetching content from {url}: {str(e)}")
            raise
    
    def _clean_text(self, text: str) -> str:
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())
        # Remove HTML entities
        text = re.sub(r'&[a-zA-Z0-9#]+;', '', text)
        return text
    
    def _extract_metadata(self, html: str) -> Dict[str, Any]:
        metadata = {}
        
        # Extract meta tags
        meta_patterns = {
            'description': r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
            'keywords': r'<meta[^>]*name=["\']keywords["\'][^>]*content=["\']([^"\']*)["\']',
            'author': r'<meta[^>]*name=["\']author["\'][^>]*content=["\']([^"\']*)["\']',
            'og:title': r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']*)["\']',
            'og:description': r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']*)["\']',
            'og:image': r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']*)["\']',
        }
        
        for key, pattern in meta_patterns.items():
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                metadata[key] = match.group(1)
        
        return metadata


class TwitterContentExtractor(BaseContentExtractor):
    async def extract(self, url: str) -> ExtractedContent:
        # For Twitter, we would need to use the API or scraping
        # This is a placeholder implementation
        html = await self._fetch_content(url)
        
        # Extract tweet content (simplified)
        tweet_match = re.search(r'<div[^>]*data-testid=["\']tweetText["\'][^>]*>(.*?)</div>', html, re.DOTALL)
        content = tweet_match.group(1) if tweet_match else ""
        
        # Extract author
        author_match = re.search(r'<span[^>]*>@([^<]+)</span>', html)
        author = author_match.group(1) if author_match else ""
        
        # Extract title (usually first part of tweet)
        title = content[:100] + "..." if len(content) > 100 else content
        
        metadata = self._extract_metadata(html)
        
        return ExtractedContent(
            title=self._clean_text(title),
            content=self._clean_text(content),
            author=author,
            published_date=None,  # Would need to extract from HTML or API
            metadata=metadata,
            media_urls=[],
            extracted_at=datetime.now()
        )


class YouTubeContentExtractor(BaseContentExtractor):
    async def extract(self, url: str) -> ExtractedContent:
        html = await self._fetch_content(url)
        
        # Extract video title
        title_match = re.search(r'<title>([^<]+)</title>', html)
        title = title_match.group(1) if title_match else ""
        
        # Extract description
        desc_match = re.search(r'"description":{"simpleText":"([^"]+)"', html)
        content = desc_match.group(1) if desc_match else ""
        
        # Extract author
        author_match = re.search(r'"author":"([^"]+)"', html)
        author = author_match.group(1) if author_match else ""
        
        metadata = self._extract_metadata(html)
        
        return ExtractedContent(
            title=self._clean_text(title),
            content=self._clean_text(content),
            author=author,
            published_date=None,
            metadata=metadata,
            media_urls=[url],
            extracted_at=datetime.now()
        )


class GenericWebContentExtractor(BaseContentExtractor):
    async def extract(self, url: str) -> ExtractedContent:
        html = await self._fetch_content(url)
        
        # Extract title
        title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1) if title_match else ""
        
        # Extract main content (simplified approach)
        # Remove script and style tags
        content = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Extract text from paragraphs
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', content, re.DOTALL | re.IGNORECASE)
        content_text = ' '.join(paragraphs)
        
        # Remove HTML tags
        content_text = re.sub(r'<[^>]+>', '', content_text)
        
        metadata = self._extract_metadata(html)
        author = metadata.get('author', '')
        
        return ExtractedContent(
            title=self._clean_text(title),
            content=self._clean_text(content_text),
            author=author,
            published_date=None,
            metadata=metadata,
            media_urls=[],
            extracted_at=datetime.now()
        )


class ContentExtractorFactory:
    @staticmethod
    def get_extractor(url: str) -> BaseContentExtractor:
        domain = urlparse(url).netloc.lower()
        
        if 'twitter.com' in domain or 'x.com' in domain:
            return TwitterContentExtractor()
        elif 'youtube.com' in domain or 'youtu.be' in domain:
            return YouTubeContentExtractor()
        else:
            return GenericWebContentExtractor()


class ContentExtractor:
    def __init__(self):
        self.logger = get_logger(__name__)
    
    async def extract_content(self, url: str) -> ExtractedContent:
        extractor = ContentExtractorFactory.get_extractor(url)
        
        try:
            async with extractor:
                return await extractor.extract(url)
        except Exception as e:
            self.logger.error(f"Error extracting content from {url}: {str(e)}")
            raise
    
    async def extract_multiple(self, urls: List[str]) -> List[ExtractedContent]:
        results = []
        
        # Process in batches to avoid overwhelming the server
        batch_size = 10
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            batch_tasks = [self.extract_content(url) for url in batch]
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, Exception):
                    self.logger.error(f"Error in batch processing: {str(result)}")
                else:
                    results.append(result)
            
            # Add delay between batches
            await asyncio.sleep(1)
        
        return results