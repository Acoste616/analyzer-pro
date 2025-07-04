"""Tweet content extractor for X/Twitter bookmarks."""

import re
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, parse_qs
import asyncio

import pandas as pd
import aiohttp
from bs4 import BeautifulSoup

from ..utils.logger import get_logger, log_execution_time
from ..utils.validation import (
    validate_bookmark_data,
    is_video_url,
    extract_domain,
    estimate_reading_time,
)

logger = get_logger(__name__)


class TweetExtractor:
    """Extract and process tweet content from bookmarks."""
    
    def __init__(self, expand_urls: bool = True, extract_media: bool = True):
        """
        Initialize tweet extractor.
        
        Args:
            expand_urls: Whether to expand shortened URLs
            extract_media: Whether to extract media information
        """
        self.expand_urls = expand_urls
        self.extract_media = extract_media
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    @log_execution_time
    async def extract_from_csv(self, csv_path: Path) -> List[Dict[str, Any]]:
        """
        Extract tweets from CSV file.
        
        Args:
            csv_path: Path to CSV file with bookmarks
            
        Returns:
            List of extracted tweet data
        """
        logger.info(f"Extracting tweets from CSV: {csv_path}")
        
        # Read CSV file
        try:
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded {len(df)} bookmarks from CSV")
        except Exception as e:
            logger.error(f"Failed to read CSV: {e}")
            raise
        
        # Process each bookmark
        tweets = []
        for idx, row in df.iterrows():
            try:
                tweet_data = await self._process_bookmark_row(row)
                if tweet_data:
                    tweets.append(tweet_data)
            except Exception as e:
                logger.error(f"Failed to process row {idx}: {e}")
                continue
        
        logger.info(f"Successfully extracted {len(tweets)} tweets")
        return tweets
    
    async def extract_from_json(self, json_path: Path) -> List[Dict[str, Any]]:
        """
        Extract tweets from JSON file.
        
        Args:
            json_path: Path to JSON file with bookmarks
            
        Returns:
            List of extracted tweet data
        """
        logger.info(f"Extracting tweets from JSON: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle different JSON structures
        bookmarks = data if isinstance(data, list) else data.get('bookmarks', [])
        
        tweets = []
        for bookmark in bookmarks:
            try:
                tweet_data = await self._process_bookmark_dict(bookmark)
                if tweet_data:
                    tweets.append(tweet_data)
            except Exception as e:
                logger.error(f"Failed to process bookmark: {e}")
                continue
        
        logger.info(f"Successfully extracted {len(tweets)} tweets")
        return tweets
    
    async def _process_bookmark_row(self, row: pd.Series) -> Optional[Dict[str, Any]]:
        """Process a single bookmark row from CSV."""
        # Common CSV column mappings
        url = row.get('url') or row.get('link') or row.get('tweet_url')
        if not url:
            return None
        
        bookmark_data = {
            'id': row.get('id') or self._extract_tweet_id(url),
            'url': url,
            'title': row.get('title') or row.get('text') or '',
            'content': row.get('content') or row.get('full_text') or '',
            'author': row.get('author') or row.get('username') or self._extract_username(url),
            'created_at': row.get('created_at') or row.get('date') or '',
        }
        
        return await self._enrich_tweet_data(bookmark_data)
    
    async def _process_bookmark_dict(self, bookmark: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single bookmark dictionary from JSON."""
        url = bookmark.get('url')
        if not url:
            return None
        
        bookmark_data = {
            'id': bookmark.get('id') or self._extract_tweet_id(url),
            'url': url,
            'title': bookmark.get('title', ''),
            'content': bookmark.get('content', ''),
            'author': bookmark.get('author') or self._extract_username(url),
            'created_at': bookmark.get('created_at', ''),
            'metadata': bookmark.get('metadata', {}),
        }
        
        return await self._enrich_tweet_data(bookmark_data)
    
    async def _enrich_tweet_data(self, tweet_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Enrich tweet data with additional information.
        
        Args:
            tweet_data: Basic tweet data
            
        Returns:
            Enriched tweet data
        """
        # Validate data
        validated = validate_bookmark_data(tweet_data)
        if not validated:
            return None
        
        # Extract tweet ID and username
        tweet_id = self._extract_tweet_id(tweet_data['url'])
        username = self._extract_username(tweet_data['url'])
        
        # Enrich data
        enriched = {
            'id': tweet_id,
            'url': tweet_data['url'],
            'author': username or tweet_data.get('author'),
            'content': tweet_data.get('content', ''),
            'created_at': tweet_data.get('created_at'),
            'type': 'tweet',
            'metadata': {
                'original_url': tweet_data['url'],
                'is_thread': False,  # Will be determined by thread extractor
                'has_media': False,
                'media_urls': [],
                'mentioned_users': [],
                'hashtags': [],
                'urls': [],
            }
        }
        
        # Extract entities from content
        if enriched['content']:
            enriched['metadata'].update(self._extract_entities(enriched['content']))
            enriched['metadata']['reading_time'] = estimate_reading_time(enriched['content'])
        
        # Expand URLs if enabled
        if self.expand_urls and enriched['metadata']['urls']:
            enriched['metadata']['expanded_urls'] = await self._expand_urls(
                enriched['metadata']['urls']
            )
        
        return enriched
    
    def _extract_tweet_id(self, url: str) -> Optional[str]:
        """Extract tweet ID from URL."""
        patterns = [
            r'twitter\.com/\w+/status/(\d+)',
            r'x\.com/\w+/status/(\d+)',
            r't\.co/(\w+)',  # Short URL
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_username(self, url: str) -> Optional[str]:
        """Extract username from URL."""
        patterns = [
            r'twitter\.com/(\w+)/status/',
            r'x\.com/(\w+)/status/',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_entities(self, content: str) -> Dict[str, Any]:
        """Extract entities (mentions, hashtags, URLs) from tweet content."""
        entities = {
            'mentioned_users': re.findall(r'@(\w+)', content),
            'hashtags': re.findall(r'#(\w+)', content),
            'urls': re.findall(r'https?://\S+', content),
        }
        
                         # Check for media indicators
        media_indicators = ['pic.twitter.com', 'video', 'gif', '🎥', '📸', '🖼️']
        has_media = any(indicator in content.lower() for indicator in media_indicators)
        
        return {
            'mentioned_users': entities['mentioned_users'],
            'hashtags': entities['hashtags'],
            'urls': entities['urls'],
            'has_media': has_media,
        }
    
    async def _expand_urls(self, urls: List[str]) -> Dict[str, str]:
        """
        Expand shortened URLs.
        
        Args:
            urls: List of URLs to expand
            
        Returns:
            Mapping of short URL to expanded URL
        """
        if not self.session:
            return {}
        
        expanded = {}
        
        for url in urls:
            if 't.co' in url or 'bit.ly' in url:
                try:
                    async with self.session.head(url, allow_redirects=True) as response:
                        expanded[url] = str(response.url)
                except Exception as e:
                    logger.debug(f"Failed to expand URL {url}: {e}")
                    expanded[url] = url
            else:
                expanded[url] = url
        
        return expanded
    
    async def extract_tweet_details(self, tweet_url: str) -> Optional[Dict[str, Any]]:
        """
        Extract detailed information from a tweet URL.
        
        Args:
            tweet_url: URL of the tweet
            
        Returns:
            Detailed tweet information
        """
        # This would typically use Twitter API or web scraping
        # For now, return basic structure
        tweet_id = self._extract_tweet_id(tweet_url)
        username = self._extract_username(tweet_url)
        
        if not tweet_id or not username:
            return None
        
        return {
            'id': tweet_id,
            'url': tweet_url,
            'author': username,
            'type': 'tweet',
            'metadata': {
                'requires_api_fetch': True,
                'fetch_timestamp': datetime.now().isoformat(),
            }
        }
    
    def extract_media_info(self, content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract media information from tweet content.
        
        Args:
            content: Tweet content
            metadata: Existing metadata
            
        Returns:
            Updated metadata with media info
        """
        media_info = {
            'images': [],
            'videos': [],
            'gifs': [],
            'links': [],
        }
        
        # Extract image URLs
        image_patterns = [
            r'pic\.twitter\.com/\w+',
            r'pbs\.twimg\.com/media/[\w-]+',
        ]
        
        for pattern in image_patterns:
            matches = re.findall(pattern, content)
            media_info['images'].extend(matches)
        
        # Check for video indicators
        if any(word in content.lower() for word in ['video', 'watch', 'clip']):
            media_info['videos'].append('possible_video_content')
        
        # Extract external links
        urls = metadata.get('urls', [])
        for url in urls:
            domain = extract_domain(url)
            if domain and is_video_url(url):
                media_info['videos'].append(url)
            elif domain and domain not in ['twitter.com', 'x.com', 't.co']:
                media_info['links'].append(url)
        
        return media_info
    
    def categorize_tweet_type(self, tweet_data: Dict[str, Any]) -> str:
        """
        Categorize the type of tweet.
        
        Args:
            tweet_data: Tweet data
            
        Returns:
            Tweet category
        """
        content = tweet_data.get('content', '').lower()
        metadata = tweet_data.get('metadata', {})
        
        # Check for thread
        if '🧵' in content or 'thread' in content or '1/' in content:
            return 'thread_start'
        
        # Check for reply
        if content.startswith('@') or metadata.get('in_reply_to'):
            return 'reply'
        
        # Check for quote tweet
        if 'quoted_tweet' in metadata or 'QT' in content:
            return 'quote_tweet'
        
        # Check for media
        if metadata.get('has_media') or metadata.get('media_urls'):
            if 'video' in str(metadata):
                return 'video_tweet'
            else:
                return 'image_tweet'
        
        # Check for link sharing
        if metadata.get('urls'):
            return 'link_tweet'
        
        return 'text_tweet'
    
    def batch_process_tweets(
        self,
        tweets: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> List[List[Dict[str, Any]]]:
        """
        Split tweets into batches for processing.
        
        Args:
            tweets: List of tweets
            batch_size: Size of each batch
            
        Returns:
            List of batches
        """
        return [tweets[i:i + batch_size] for i in range(0, len(tweets), batch_size)]