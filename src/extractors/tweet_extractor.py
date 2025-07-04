import re
import json
import aiohttp
from typing import Dict, Any, Optional, List
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from ..config.settings import settings_manager
from ..utils.logger import get_logger
from ..utils.validation import validate_url


class TweetExtractor:
    def __init__(self):
        self.settings = settings_manager.settings
        self.logger = get_logger(__name__)
        self.session = None
        
        # Twitter API configuration
        self.twitter_config = self.settings.extractors.get('twitter', {})
        self.base_url = self.twitter_config.get('base_url', 'https://api.twitter.com/2')
        self.timeout = self.twitter_config.get('timeout', 30)
        
        # Rate limiting
        self.rate_limit = self.twitter_config.get('rate_limit', {})
        self.requests_per_minute = self.rate_limit.get('requests_per_minute', 300)
        
        # Headers for web scraping fallback
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=100)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.headers
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def extract(self, bookmark_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract tweet content from URL or existing data
        
        Args:
            bookmark_data: Dictionary containing tweet URL and any existing data
            
        Returns:
            Dictionary with extracted tweet data
        """
        url = bookmark_data.get('url', '')
        if not validate_url(url):
            raise ValueError(f"Invalid URL: {url}")
        
        # Check if this is a Twitter/X URL
        if not self._is_twitter_url(url):
            raise ValueError(f"Not a Twitter URL: {url}")
        
        # Extract tweet ID from URL
        tweet_id = self._extract_tweet_id(url)
        if not tweet_id:
            raise ValueError(f"Could not extract tweet ID from URL: {url}")
        
        try:
            # Try different extraction methods
            extracted_data = await self._extract_from_web_scraping(url)
            
            # If web scraping fails, use fallback methods
            if not extracted_data.get('content'):
                extracted_data = await self._extract_from_oembed(url)
            
            # Enhance with additional metadata
            extracted_data = self._enhance_tweet_data(extracted_data, tweet_id, url)
            
            return extracted_data
            
        except Exception as e:
            self.logger.error(f"Error extracting tweet from {url}: {str(e)}")
            # Return basic data structure
            return {
                'title': f"Tweet {tweet_id}",
                'content': bookmark_data.get('content', ''),
                'author': bookmark_data.get('author', ''),
                'metadata': {
                    'tweet_id': tweet_id,
                    'url': url,
                    'extraction_method': 'fallback',
                    'error': str(e)
                }
            }
    
    def _is_twitter_url(self, url: str) -> bool:
        """Check if URL is from Twitter/X"""
        parsed = urlparse(url)
        return parsed.netloc.lower() in ['twitter.com', 'x.com', 'www.twitter.com', 'www.x.com']
    
    def _extract_tweet_id(self, url: str) -> Optional[str]:
        """Extract tweet ID from Twitter URL"""
        # Pattern for tweet URLs: https://twitter.com/username/status/1234567890
        # or https://x.com/username/status/1234567890
        pattern = r'/status/(\d+)'
        match = re.search(pattern, url)
        return match.group(1) if match else None
    
    async def _extract_from_web_scraping(self, url: str) -> Dict[str, Any]:
        """Extract tweet data using web scraping"""
        
        if not self.session:
            raise ValueError("Session not initialized. Use 'async with' context manager.")
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                html = await response.text()
                
                # Extract tweet data from HTML
                extracted_data = {
                    'title': self._extract_title(html),
                    'content': self._extract_content(html),
                    'author': self._extract_author(html),
                    'published_date': self._extract_published_date(html),
                    'metadata': self._extract_metadata_from_html(html)
                }
                
                return extracted_data
                
        except Exception as e:
            self.logger.error(f"Web scraping failed for {url}: {str(e)}")
            raise
    
    def _extract_title(self, html: str) -> str:
        """Extract tweet title from HTML"""
        # Try different title extraction methods
        patterns = [
            r'<title>([^<]+)</title>',
            r'<meta property="og:title" content="([^"]+)"',
            r'<meta name="twitter:title" content="([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                title = match.group(1).strip()
                # Clean up title
                title = re.sub(r'\s+', ' ', title)
                title = title.replace(' / X', '').replace(' / Twitter', '')
                return title
        
        return "Tweet"
    
    def _extract_content(self, html: str) -> str:
        """Extract tweet content from HTML"""
        # Try different content extraction methods
        patterns = [
            r'<div[^>]*data-testid=["\']tweetText["\'][^>]*>(.*?)</div>',
            r'<div[^>]*class=["\'][^"\']*tweet-text[^"\']*["\'][^>]*>(.*?)</div>',
            r'<p[^>]*class=["\'][^"\']*tweet-text[^"\']*["\'][^>]*>(.*?)</p>',
            r'<meta property="og:description" content="([^"]+)"',
            r'<meta name="twitter:description" content="([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                content = match.group(1).strip()
                # Clean HTML tags
                content = re.sub(r'<[^>]+>', '', content)
                # Decode HTML entities
                content = content.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                # Clean up whitespace
                content = re.sub(r'\s+', ' ', content).strip()
                
                if content and len(content) > 10:  # Ensure we have meaningful content
                    return content
        
        return ""
    
    def _extract_author(self, html: str) -> str:
        """Extract tweet author from HTML"""
        patterns = [
            r'<div[^>]*data-testid=["\']User-Names["\'][^>]*>.*?<span[^>]*>@([^<]+)</span>',
            r'<a[^>]*href=["\']https://(?:twitter\.com|x\.com)/([^/"\'\?]+)',
            r'<meta name="twitter:creator" content="@([^"]+)"',
            r'<meta property="twitter:creator" content="@([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                author = match.group(1).strip()
                # Remove @ symbol if present
                author = author.lstrip('@')
                return author
        
        return ""
    
    def _extract_published_date(self, html: str) -> Optional[datetime]:
        """Extract tweet published date from HTML"""
        patterns = [
            r'<time[^>]*datetime=["\']([^"\']+)["\']',
            r'<meta property="article:published_time" content="([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                try:
                    # Parse ISO format datetime
                    if 'T' in date_str:
                        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        return datetime.fromisoformat(date_str)
                except ValueError:
                    continue
        
        return None
    
    def _extract_metadata_from_html(self, html: str) -> Dict[str, Any]:
        """Extract additional metadata from HTML"""
        metadata = {}
        
        # Extract reply count
        reply_pattern = r'<div[^>]*data-testid=["\']reply["\'][^>]*>.*?(\d+)'
        reply_match = re.search(reply_pattern, html, re.IGNORECASE | re.DOTALL)
        if reply_match:
            metadata['reply_count'] = int(reply_match.group(1))
        
        # Extract retweet count
        retweet_pattern = r'<div[^>]*data-testid=["\']retweet["\'][^>]*>.*?(\d+)'
        retweet_match = re.search(retweet_pattern, html, re.IGNORECASE | re.DOTALL)
        if retweet_match:
            metadata['retweet_count'] = int(retweet_match.group(1))
        
        # Extract like count
        like_pattern = r'<div[^>]*data-testid=["\']like["\'][^>]*>.*?(\d+)'
        like_match = re.search(like_pattern, html, re.IGNORECASE | re.DOTALL)
        if like_match:
            metadata['like_count'] = int(like_match.group(1))
        
        # Extract hashtags
        hashtag_pattern = r'#(\w+)'
        hashtags = re.findall(hashtag_pattern, html)
        if hashtags:
            metadata['hashtags'] = list(set(hashtags))
        
        # Extract mentions
        mention_pattern = r'@(\w+)'
        mentions = re.findall(mention_pattern, html)
        if mentions:
            metadata['mentions'] = list(set(mentions))
        
        # Extract media URLs
        media_patterns = [
            r'<img[^>]*src=["\']([^"\']+)["\']',
            r'<video[^>]*src=["\']([^"\']+)["\']'
        ]
        
        media_urls = []
        for pattern in media_patterns:
            urls = re.findall(pattern, html)
            for url in urls:
                if 'pbs.twimg.com' in url or 'video.twimg.com' in url:
                    media_urls.append(url)
        
        if media_urls:
            metadata['media_urls'] = media_urls
        
        return metadata
    
    async def _extract_from_oembed(self, url: str) -> Dict[str, Any]:
        """Extract tweet data using oEmbed API"""
        
        oembed_url = f"https://publish.twitter.com/oembed?url={url}"
        
        try:
            async with self.session.get(oembed_url) as response:
                if response.status != 200:
                    raise Exception(f"oEmbed HTTP {response.status}")
                
                oembed_data = await response.json()
                
                # Extract data from oEmbed response
                extracted_data = {
                    'title': oembed_data.get('author_name', 'Tweet'),
                    'content': self._clean_html(oembed_data.get('html', '')),
                    'author': oembed_data.get('author_name', ''),
                    'published_date': None,
                    'metadata': {
                        'author_url': oembed_data.get('author_url', ''),
                        'provider_name': oembed_data.get('provider_name', ''),
                        'provider_url': oembed_data.get('provider_url', ''),
                        'width': oembed_data.get('width'),
                        'height': oembed_data.get('height'),
                        'html': oembed_data.get('html', '')
                    }
                }
                
                return extracted_data
                
        except Exception as e:
            self.logger.error(f"oEmbed extraction failed for {url}: {str(e)}")
            raise
    
    def _clean_html(self, html: str) -> str:
        """Clean HTML content to extract text"""
        if not html:
            return ""
        
        # Remove script and style tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags
        html = re.sub(r'<[^>]+>', '', html)
        
        # Decode HTML entities
        html = html.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        html = html.replace('&nbsp;', ' ')
        
        # Clean up whitespace
        html = re.sub(r'\s+', ' ', html).strip()
        
        return html
    
    def _enhance_tweet_data(self, data: Dict[str, Any], tweet_id: str, url: str) -> Dict[str, Any]:
        """Enhance tweet data with additional processing"""
        
        # Add tweet ID to metadata
        if 'metadata' not in data:
            data['metadata'] = {}
        
        data['metadata']['tweet_id'] = tweet_id
        data['metadata']['original_url'] = url
        data['metadata']['extraction_method'] = 'web_scraping'
        data['metadata']['extracted_at'] = datetime.now().isoformat()
        
        # Enhance title if it's generic
        if data.get('title') == 'Tweet' and data.get('content'):
            # Use first 50 characters of content as title
            content_title = data['content'][:50]
            if len(data['content']) > 50:
                content_title += '...'
            data['title'] = f"Tweet by {data.get('author', 'Unknown')}: {content_title}"
        
        # Add content type
        data['metadata']['content_type'] = 'tweet'
        
        # Add engagement metrics if available
        engagement_metrics = {}
        metadata = data.get('metadata', {})
        
        if 'reply_count' in metadata:
            engagement_metrics['replies'] = metadata['reply_count']
        if 'retweet_count' in metadata:
            engagement_metrics['retweets'] = metadata['retweet_count']
        if 'like_count' in metadata:
            engagement_metrics['likes'] = metadata['like_count']
        
        if engagement_metrics:
            data['metadata']['engagement'] = engagement_metrics
        
        return data
    
    def get_tweet_metrics(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get engagement metrics from extracted tweet data"""
        
        metadata = extracted_data.get('metadata', {})
        engagement = metadata.get('engagement', {})
        
        return {
            'replies': engagement.get('replies', 0),
            'retweets': engagement.get('retweets', 0),
            'likes': engagement.get('likes', 0),
            'total_engagement': sum(engagement.values()) if engagement else 0
        }
    
    def is_retweet(self, extracted_data: Dict[str, Any]) -> bool:
        """Check if the tweet is a retweet"""
        content = extracted_data.get('content', '')
        return content.startswith('RT @') or 'retweeted' in content.lower()
    
    def is_reply(self, extracted_data: Dict[str, Any]) -> bool:
        """Check if the tweet is a reply"""
        content = extracted_data.get('content', '')
        return content.startswith('@') or 'replying to' in content.lower()
    
    def get_hashtags(self, extracted_data: Dict[str, Any]) -> List[str]:
        """Get hashtags from extracted tweet data"""
        metadata = extracted_data.get('metadata', {})
        hashtags = metadata.get('hashtags', [])
        
        # Also extract from content if not in metadata
        content = extracted_data.get('content', '')
        content_hashtags = re.findall(r'#(\w+)', content)
        
        # Combine and deduplicate
        all_hashtags = list(set(hashtags + content_hashtags))
        return all_hashtags
    
    def get_mentions(self, extracted_data: Dict[str, Any]) -> List[str]:
        """Get mentions from extracted tweet data"""
        metadata = extracted_data.get('metadata', {})
        mentions = metadata.get('mentions', [])
        
        # Also extract from content if not in metadata
        content = extracted_data.get('content', '')
        content_mentions = re.findall(r'@(\w+)', content)
        
        # Combine and deduplicate
        all_mentions = list(set(mentions + content_mentions))
        return all_mentions