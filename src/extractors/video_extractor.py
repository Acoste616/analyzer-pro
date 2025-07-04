import re
import json
import aiohttp
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

from ..config.settings import settings_manager
from ..utils.logger import get_logger
from ..utils.validation import validate_url


class VideoExtractor:
    def __init__(self):
        self.settings = settings_manager.settings
        self.logger = get_logger(__name__)
        self.session = None
        
        # Configuration
        self.web_config = self.settings.extractors.get('web_scraping', {})
        self.timeout = self.web_config.get('timeout', 30)
        
        # Headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Platform-specific extractors
        self.platform_extractors = {
            'youtube': self._extract_youtube,
            'vimeo': self._extract_vimeo,
            'dailymotion': self._extract_dailymotion,
            'twitch': self._extract_twitch,
            'tiktok': self._extract_tiktok
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
        Extract video content from URL or existing data
        
        Args:
            bookmark_data: Dictionary containing video URL and any existing data
            
        Returns:
            Dictionary with extracted video data
        """
        url = bookmark_data.get('url', '')
        if not validate_url(url):
            raise ValueError(f"Invalid URL: {url}")
        
        # Determine video platform
        platform = self._identify_platform(url)
        if not platform:
            raise ValueError(f"Unsupported video platform: {url}")
        
        try:
            # Extract using platform-specific extractor
            extractor = self.platform_extractors.get(platform)
            if extractor:
                extracted_data = await extractor(url)
            else:
                extracted_data = await self._extract_generic_video(url)
            
            # Enhance with additional metadata
            extracted_data = self._enhance_video_data(extracted_data, platform, url)
            
            return extracted_data
            
        except Exception as e:
            self.logger.error(f"Error extracting video from {url}: {str(e)}")
            # Return basic data structure
            return {
                'title': f"Video from {platform or 'Unknown'}",
                'content': bookmark_data.get('content', ''),
                'author': bookmark_data.get('author', ''),
                'metadata': {
                    'platform': platform,
                    'url': url,
                    'extraction_method': 'fallback',
                    'error': str(e)
                }
            }
    
    def _identify_platform(self, url: str) -> Optional[str]:
        """Identify video platform from URL"""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        if 'youtube.com' in domain or 'youtu.be' in domain:
            return 'youtube'
        elif 'vimeo.com' in domain:
            return 'vimeo'
        elif 'dailymotion.com' in domain:
            return 'dailymotion'
        elif 'twitch.tv' in domain:
            return 'twitch'
        elif 'tiktok.com' in domain:
            return 'tiktok'
        else:
            return None
    
    async def _extract_youtube(self, url: str) -> Dict[str, Any]:
        """Extract YouTube video data"""
        
        # Extract video ID
        video_id = self._extract_youtube_video_id(url)
        if not video_id:
            raise ValueError(f"Could not extract YouTube video ID from: {url}")
        
        # Fetch video page
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        
        try:
            async with self.session.get(watch_url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                html = await response.text()
                
                # Extract video data
                extracted_data = {
                    'title': self._extract_youtube_title(html),
                    'content': self._extract_youtube_description(html),
                    'author': self._extract_youtube_channel(html),
                    'published_date': self._extract_youtube_publish_date(html),
                    'metadata': self._extract_youtube_metadata(html, video_id)
                }
                
                return extracted_data
                
        except Exception as e:
            self.logger.error(f"YouTube extraction failed for {url}: {str(e)}")
            raise
    
    def _extract_youtube_video_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/v/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_youtube_title(self, html: str) -> str:
        """Extract YouTube video title"""
        patterns = [
            r'"title":"([^"]+)"',
            r'<title>([^<]+)</title>',
            r'<meta property="og:title" content="([^"]+)"',
            r'<meta name="title" content="([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                # Clean up YouTube title
                title = title.replace(' - YouTube', '')
                title = re.sub(r'\s+', ' ', title)
                # Decode unicode escapes
                title = title.encode().decode('unicode_escape')
                return title
        
        return "YouTube Video"
    
    def _extract_youtube_description(self, html: str) -> str:
        """Extract YouTube video description"""
        patterns = [
            r'"description":{"simpleText":"([^"]+)"}',
            r'"shortDescription":"([^"]+)"',
            r'<meta property="og:description" content="([^"]+)"',
            r'<meta name="description" content="([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                description = match.group(1).strip()
                # Decode unicode escapes
                description = description.encode().decode('unicode_escape')
                # Clean up
                description = re.sub(r'\\n', '\n', description)
                description = re.sub(r'\s+', ' ', description)
                return description
        
        return ""
    
    def _extract_youtube_channel(self, html: str) -> str:
        """Extract YouTube channel name"""
        patterns = [
            r'"author":"([^"]+)"',
            r'"ownerChannelName":"([^"]+)"',
            r'<link itemprop="name" content="([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                channel = match.group(1).strip()
                # Decode unicode escapes
                channel = channel.encode().decode('unicode_escape')
                return channel
        
        return ""
    
    def _extract_youtube_publish_date(self, html: str) -> Optional[datetime]:
        """Extract YouTube video publish date"""
        patterns = [
            r'"publishDate":"([^"]+)"',
            r'"uploadDate":"([^"]+)"',
            r'<meta itemprop="uploadDate" content="([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                try:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    continue
        
        return None
    
    def _extract_youtube_metadata(self, html: str, video_id: str) -> Dict[str, Any]:
        """Extract YouTube video metadata"""
        metadata = {
            'video_id': video_id,
            'platform': 'youtube',
            'content_type': 'video'
        }
        
        # Extract duration
        duration_pattern = r'"lengthSeconds":"(\d+)"'
        duration_match = re.search(duration_pattern, html)
        if duration_match:
            duration_seconds = int(duration_match.group(1))
            metadata['duration_seconds'] = duration_seconds
            metadata['duration_formatted'] = self._format_duration(duration_seconds)
        
        # Extract view count
        view_pattern = r'"viewCount":"(\d+)"'
        view_match = re.search(view_pattern, html)
        if view_match:
            metadata['view_count'] = int(view_match.group(1))
        
        # Extract like count (if available)
        like_pattern = r'"likes":{"simpleText":"([^"]+)"}'
        like_match = re.search(like_pattern, html)
        if like_match:
            like_text = like_match.group(1)
            # Parse likes (might be in format like "1.2K")
            metadata['like_count_text'] = like_text
        
        # Extract category
        category_pattern = r'"category":"([^"]+)"'
        category_match = re.search(category_pattern, html)
        if category_match:
            metadata['category'] = category_match.group(1)
        
        # Extract tags
        tag_pattern = r'"keywords":\[([^\]]+)\]'
        tag_match = re.search(tag_pattern, html)
        if tag_match:
            tags_text = tag_match.group(1)
            # Parse tags
            tags = re.findall(r'"([^"]+)"', tags_text)
            metadata['tags'] = tags
        
        # Extract thumbnail
        thumbnail_pattern = r'"thumbnails":\[{"url":"([^"]+)"'
        thumbnail_match = re.search(thumbnail_pattern, html)
        if thumbnail_match:
            metadata['thumbnail_url'] = thumbnail_match.group(1)
        
        return metadata
    
    async def _extract_vimeo(self, url: str) -> Dict[str, Any]:
        """Extract Vimeo video data"""
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                html = await response.text()
                
                # Extract video data
                extracted_data = {
                    'title': self._extract_generic_title(html),
                    'content': self._extract_generic_description(html),
                    'author': self._extract_vimeo_author(html),
                    'published_date': self._extract_generic_publish_date(html),
                    'metadata': self._extract_vimeo_metadata(html, url)
                }
                
                return extracted_data
                
        except Exception as e:
            self.logger.error(f"Vimeo extraction failed for {url}: {str(e)}")
            raise
    
    def _extract_vimeo_author(self, html: str) -> str:
        """Extract Vimeo author"""
        patterns = [
            r'"name":"([^"]+)"',
            r'<meta property="video:actor" content="([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _extract_vimeo_metadata(self, html: str, url: str) -> Dict[str, Any]:
        """Extract Vimeo metadata"""
        metadata = {
            'platform': 'vimeo',
            'content_type': 'video',
            'url': url
        }
        
        # Extract video ID
        video_id_match = re.search(r'vimeo\.com/(\d+)', url)
        if video_id_match:
            metadata['video_id'] = video_id_match.group(1)
        
        # Extract duration
        duration_pattern = r'"duration":(\d+)'
        duration_match = re.search(duration_pattern, html)
        if duration_match:
            duration_seconds = int(duration_match.group(1))
            metadata['duration_seconds'] = duration_seconds
            metadata['duration_formatted'] = self._format_duration(duration_seconds)
        
        return metadata
    
    async def _extract_dailymotion(self, url: str) -> Dict[str, Any]:
        """Extract Dailymotion video data"""
        return await self._extract_generic_video(url, platform='dailymotion')
    
    async def _extract_twitch(self, url: str) -> Dict[str, Any]:
        """Extract Twitch video/stream data"""
        return await self._extract_generic_video(url, platform='twitch')
    
    async def _extract_tiktok(self, url: str) -> Dict[str, Any]:
        """Extract TikTok video data"""
        return await self._extract_generic_video(url, platform='tiktok')
    
    async def _extract_generic_video(self, url: str, platform: str = 'generic') -> Dict[str, Any]:
        """Generic video extraction for unsupported platforms"""
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                html = await response.text()
                
                # Extract basic video data
                extracted_data = {
                    'title': self._extract_generic_title(html),
                    'content': self._extract_generic_description(html),
                    'author': self._extract_generic_author(html),
                    'published_date': self._extract_generic_publish_date(html),
                    'metadata': {
                        'platform': platform,
                        'content_type': 'video',
                        'url': url
                    }
                }
                
                return extracted_data
                
        except Exception as e:
            self.logger.error(f"Generic video extraction failed for {url}: {str(e)}")
            raise
    
    def _extract_generic_title(self, html: str) -> str:
        """Extract generic video title"""
        patterns = [
            r'<title>([^<]+)</title>',
            r'<meta property="og:title" content="([^"]+)"',
            r'<meta name="twitter:title" content="([^"]+)"',
            r'<meta name="title" content="([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                title = re.sub(r'\s+', ' ', title)
                return title
        
        return "Video"
    
    def _extract_generic_description(self, html: str) -> str:
        """Extract generic video description"""
        patterns = [
            r'<meta property="og:description" content="([^"]+)"',
            r'<meta name="twitter:description" content="([^"]+)"',
            r'<meta name="description" content="([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                description = match.group(1).strip()
                description = re.sub(r'\s+', ' ', description)
                return description
        
        return ""
    
    def _extract_generic_author(self, html: str) -> str:
        """Extract generic video author"""
        patterns = [
            r'<meta name="author" content="([^"]+)"',
            r'<meta property="video:actor" content="([^"]+)"',
            r'<meta property="article:author" content="([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _extract_generic_publish_date(self, html: str) -> Optional[datetime]:
        """Extract generic video publish date"""
        patterns = [
            r'<meta property="video:release_date" content="([^"]+)"',
            r'<meta property="article:published_time" content="([^"]+)"',
            r'<time[^>]*datetime="([^"]+)"'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                try:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    continue
        
        return None
    
    def _enhance_video_data(self, data: Dict[str, Any], platform: str, url: str) -> Dict[str, Any]:
        """Enhance video data with additional processing"""
        
        # Add platform info to metadata
        if 'metadata' not in data:
            data['metadata'] = {}
        
        data['metadata']['platform'] = platform
        data['metadata']['original_url'] = url
        data['metadata']['content_type'] = 'video'
        data['metadata']['extracted_at'] = datetime.now().isoformat()
        
        # Enhance title if generic
        if data.get('title') == 'Video' and data.get('author'):
            data['title'] = f"Video by {data['author']}"
        
        # Add estimated watch time
        duration_seconds = data.get('metadata', {}).get('duration_seconds')
        if duration_seconds:
            data['metadata']['watch_time_minutes'] = round(duration_seconds / 60, 1)
        
        return data
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration from seconds to human readable format"""
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    def get_video_metrics(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get video metrics from extracted data"""
        
        metadata = extracted_data.get('metadata', {})
        
        metrics = {
            'platform': metadata.get('platform', 'unknown'),
            'duration_seconds': metadata.get('duration_seconds', 0),
            'duration_formatted': metadata.get('duration_formatted', '0:00'),
            'view_count': metadata.get('view_count', 0),
            'like_count': metadata.get('like_count', 0),
            'watch_time_minutes': metadata.get('watch_time_minutes', 0)
        }
        
        return metrics
    
    def is_live_stream(self, extracted_data: Dict[str, Any]) -> bool:
        """Check if the video is a live stream"""
        
        title = extracted_data.get('title', '').lower()
        content = extracted_data.get('content', '').lower()
        
        live_indicators = ['live', 'streaming', 'stream', 'live stream']
        
        return any(indicator in title or indicator in content for indicator in live_indicators)
    
    def is_short_form_video(self, extracted_data: Dict[str, Any]) -> bool:
        """Check if the video is short-form content (like YouTube Shorts, TikTok)"""
        
        platform = extracted_data.get('metadata', {}).get('platform', '')
        duration_seconds = extracted_data.get('metadata', {}).get('duration_seconds', 0)
        
        # TikTok is always short-form
        if platform == 'tiktok':
            return True
        
        # YouTube Shorts are typically under 60 seconds
        if platform == 'youtube' and duration_seconds > 0 and duration_seconds <= 60:
            return True
        
        # Check for shorts indicators in title/content
        title = extracted_data.get('title', '').lower()
        shorts_indicators = ['shorts', 'short', '#shorts']
        
        return any(indicator in title for indicator in shorts_indicators)
    
    def extract_video_topics(self, extracted_data: Dict[str, Any]) -> List[str]:
        """Extract topics from video data"""
        
        topics = set()
        
        # Get tags if available
        metadata = extracted_data.get('metadata', {})
        tags = metadata.get('tags', [])
        topics.update(tag.lower() for tag in tags)
        
        # Extract from title and description
        title = extracted_data.get('title', '').lower()
        content = extracted_data.get('content', '').lower()
        combined_text = f"{title} {content}"
        
        # Common video topics
        topic_keywords = {
            'tutorial': ['tutorial', 'how to', 'guide', 'learn', 'lesson'],
            'review': ['review', 'comparison', 'vs', 'unboxing'],
            'gaming': ['game', 'gaming', 'gameplay', 'playthrough', 'walkthrough'],
            'music': ['music', 'song', 'album', 'artist', 'band'],
            'tech': ['technology', 'tech', 'gadget', 'device', 'software'],
            'entertainment': ['funny', 'comedy', 'entertainment', 'reaction'],
            'education': ['education', 'educational', 'science', 'history', 'documentary'],
            'vlog': ['vlog', 'daily', 'life', 'routine', 'day in the life']
        }
        
        for topic, keywords in topic_keywords.items():
            for keyword in keywords:
                if keyword in combined_text:
                    topics.add(topic)
                    break
        
        return list(topics)
    
    def get_video_quality_indicators(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get quality indicators for the video"""
        
        metadata = extracted_data.get('metadata', {})
        
        quality_indicators = {
            'has_description': bool(extracted_data.get('content', '').strip()),
            'has_thumbnail': bool(metadata.get('thumbnail_url')),
            'has_tags': bool(metadata.get('tags')),
            'view_count': metadata.get('view_count', 0),
            'engagement_available': bool(metadata.get('like_count') or metadata.get('like_count_text')),
            'duration_appropriate': True  # Default to True
        }
        
        # Check if duration is appropriate (not too short or too long)
        duration_seconds = metadata.get('duration_seconds', 0)
        if duration_seconds > 0:
            # Consider videos under 30 seconds or over 3 hours as potentially low quality
            quality_indicators['duration_appropriate'] = 30 <= duration_seconds <= 10800
        
        # Calculate quality score
        quality_score = sum([
            quality_indicators['has_description'],
            quality_indicators['has_thumbnail'],
            quality_indicators['has_tags'],
            quality_indicators['engagement_available'],
            quality_indicators['duration_appropriate']
        ]) / 5 * 100
        
        quality_indicators['quality_score'] = round(quality_score, 1)
        
        return quality_indicators