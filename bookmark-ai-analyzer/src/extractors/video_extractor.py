"""Video content extractor for educational videos and courses."""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, parse_qs
import asyncio

import yt_dlp
import aiohttp

from ..utils.logger import get_logger, log_execution_time
from ..utils.validation import is_video_url, extract_domain

logger = get_logger(__name__)


class VideoExtractor:
    """Extract metadata and content from video URLs."""
    
    def __init__(self, download_transcripts: bool = True, extract_chapters: bool = True):
        """
        Initialize video extractor.
        
        Args:
            download_transcripts: Whether to download video transcripts
            extract_chapters: Whether to extract chapter information
        """
        self.download_transcripts = download_transcripts
        self.extract_chapters = extract_chapters
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Configure yt-dlp
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'writesubtitles': download_transcripts,
            'writeautomaticsub': download_transcripts,
            'subtitleslangs': ['en', 'pl'],
            'skip_download': True,
        }
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    @log_execution_time
    async def extract_from_bookmarks(
        self,
        bookmarks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract video content from bookmarks.
        
        Args:
            bookmarks: List of bookmark data
            
        Returns:
            List of extracted video data
        """
        video_bookmarks = [
            bookmark for bookmark in bookmarks
            if self._is_video_bookmark(bookmark)
        ]
        
        logger.info(f"Found {len(video_bookmarks)} video bookmarks to process")
        
        videos = []
        for bookmark in video_bookmarks:
            try:
                video_data = await self.extract_video_info(bookmark['url'])
                if video_data:
                    # Merge with bookmark data
                    video_data['bookmark_id'] = bookmark.get('id')
                    video_data['bookmark_metadata'] = bookmark.get('metadata', {})
                    videos.append(video_data)
            except Exception as e:
                logger.error(f"Failed to extract video from {bookmark['url']}: {e}")
                continue
        
        logger.info(f"Successfully extracted {len(videos)} videos")
        return videos
    
    def _is_video_bookmark(self, bookmark: Dict[str, Any]) -> bool:
        """Check if bookmark contains video content."""
        url = bookmark.get('url', '')
        content = bookmark.get('content', '').lower()
        
        # Check URL
        if is_video_url(url):
            return True
        
        # Check content for video indicators
        video_indicators = ['video', 'watch', 'youtube', 'vimeo', 'course', 'tutorial']
        return any(indicator in content for indicator in video_indicators)
    
    async def extract_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract comprehensive video information.
        
        Args:
            url: Video URL
            
        Returns:
            Video data dictionary
        """
        logger.debug(f"Extracting video info from: {url}")
        
        try:
            # Use yt-dlp to extract info
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            
            if not info:
                return None
            
            # Process extracted info
            video_data = self._process_video_info(info)
            
            # Extract additional metadata based on platform
            platform = self._identify_platform(url)
            if platform:
                video_data['platform'] = platform
                video_data['metadata']['platform_specific'] = await self._extract_platform_specific(
                    url, platform, info
                )
            
            return video_data
            
        except Exception as e:
            logger.error(f"Failed to extract video info: {e}")
            return None
    
    def _process_video_info(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Process raw video info from yt-dlp."""
        # Basic info
        video_data = {
            'id': info.get('id', ''),
            'url': info.get('webpage_url', info.get('url', '')),
            'title': info.get('title', ''),
            'description': info.get('description', ''),
            'duration': info.get('duration', 0),
            'upload_date': info.get('upload_date', ''),
            'uploader': info.get('uploader', ''),
            'uploader_id': info.get('uploader_id', ''),
            'type': 'video',
            'content': '',  # Will be filled with transcript
            'metadata': {
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'comment_count': info.get('comment_count', 0),
                'categories': info.get('categories', []),
                'tags': info.get('tags', []),
                'thumbnail': info.get('thumbnail', ''),
                'subtitles_available': bool(info.get('subtitles')),
                'is_live': info.get('is_live', False),
                'was_live': info.get('was_live', False),
                'duration_string': self._format_duration(info.get('duration', 0)),
            }
        }
        
        # Extract chapters if available
        if self.extract_chapters and info.get('chapters'):
            video_data['chapters'] = self._process_chapters(info['chapters'])
            video_data['metadata']['has_chapters'] = True
        else:
            video_data['chapters'] = []
            video_data['metadata']['has_chapters'] = False
        
        # Extract subtitles/transcript
        if self.download_transcripts:
            transcript = self._extract_transcript(info)
            if transcript:
                video_data['content'] = transcript
                video_data['metadata']['has_transcript'] = True
            else:
                video_data['metadata']['has_transcript'] = False
        
        # Estimate if it's educational content
        video_data['metadata']['is_educational'] = self._is_educational_content(video_data)
        
        return video_data
    
    def _format_duration(self, duration_seconds: int) -> str:
        """Format duration in human-readable format."""
        if not duration_seconds:
            return "Unknown"
        
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        seconds = duration_seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def _process_chapters(self, chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process chapter information."""
        processed_chapters = []
        
        for i, chapter in enumerate(chapters):
            processed_chapters.append({
                'index': i,
                'title': chapter.get('title', f'Chapter {i+1}'),
                'start_time': chapter.get('start_time', 0),
                'end_time': chapter.get('end_time', 0),
                'duration': chapter.get('end_time', 0) - chapter.get('start_time', 0),
            })
        
        return processed_chapters
    
    def _extract_transcript(self, info: Dict[str, Any]) -> Optional[str]:
        """Extract transcript from video info."""
        subtitles = info.get('subtitles', {})
        automatic_captions = info.get('automatic_captions', {})
        
        # Prefer manual subtitles over automatic
        all_subs = {**automatic_captions, **subtitles}
        
        # Try to get English or Polish subtitles
        for lang in ['en', 'pl', 'en-US', 'en-GB']:
            if lang in all_subs:
                # In real implementation, would download and parse subtitle file
                # For now, return placeholder
                return f"[Transcript for {info.get('title', 'video')} would be extracted here]"
        
        return None
    
    def _identify_platform(self, url: str) -> Optional[str]:
        """Identify video platform from URL."""
        domain = extract_domain(url)
        if not domain:
            return None
        
        platform_mapping = {
            'youtube.com': 'youtube',
            'youtu.be': 'youtube',
            'vimeo.com': 'vimeo',
            'twitch.tv': 'twitch',
            'udemy.com': 'udemy',
            'coursera.org': 'coursera',
            'pluralsight.com': 'pluralsight',
            'linkedin.com': 'linkedin_learning',
            'skillshare.com': 'skillshare',
        }
        
        for platform_domain, platform_name in platform_mapping.items():
            if platform_domain in domain:
                return platform_name
        
        return 'other'
    
    async def _extract_platform_specific(
        self,
        url: str,
        platform: str,
        info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract platform-specific metadata."""
        platform_data = {}
        
        if platform == 'youtube':
            platform_data.update({
                'channel_id': info.get('channel_id', ''),
                'channel_url': info.get('channel_url', ''),
                'playlist': info.get('playlist', ''),
                'playlist_index': info.get('playlist_index', ''),
            })
        elif platform == 'udemy':
            # Extract course information
            platform_data.update({
                'course_title': info.get('series', ''),
                'lecture_number': info.get('episode_number', ''),
                'is_free': 'free' in url.lower(),
            })
        
        return platform_data
    
    def _is_educational_content(self, video_data: Dict[str, Any]) -> bool:
        """Determine if video is educational content."""
        educational_indicators = [
            'tutorial', 'course', 'lesson', 'lecture', 'learn',
            'teach', 'education', 'training', 'workshop', 'masterclass',
            'how to', 'guide', 'walkthrough', 'explained', 'introduction'
        ]
        
        # Check title and description
        title = video_data.get('title', '').lower()
        description = video_data.get('description', '').lower()
        tags = [tag.lower() for tag in video_data.get('metadata', {}).get('tags', [])]
        
        # Check for indicators
        for indicator in educational_indicators:
            if indicator in title or indicator in description:
                return True
            if any(indicator in tag for tag in tags):
                return True
        
        # Check categories
        categories = video_data.get('metadata', {}).get('categories', [])
        educational_categories = ['Education', 'Science & Technology', 'Howto & Style']
        if any(cat in educational_categories for cat in categories):
            return True
        
        # Check duration (educational content tends to be longer)
        duration = video_data.get('duration', 0)
        if duration > 600:  # More than 10 minutes
            return True
        
        return False
    
    def categorize_video_content(self, video_data: Dict[str, Any]) -> str:
        """
        Categorize video content type.
        
        Args:
            video_data: Video data
            
        Returns:
            Content category
        """
        title = video_data.get('title', '').lower()
        description = video_data.get('description', '').lower()
        duration = video_data.get('duration', 0)
        
        # Course detection
        if any(word in title for word in ['course', 'bootcamp', 'masterclass']):
            return 'course'
        
        # Tutorial detection
        if any(word in title for word in ['tutorial', 'how to', 'guide']):
            return 'tutorial'
        
        # Lecture detection
        if 'lecture' in title or duration > 2700:  # > 45 minutes
            return 'lecture'
        
        # Workshop/webinar detection
        if any(word in title for word in ['workshop', 'webinar']):
            return 'workshop'
        
        # Short educational content
        if duration < 600:  # < 10 minutes
            return 'short_educational'
        
        return 'general_video'
    
    def extract_learning_structure(self, video_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract learning structure from video.
        
        Args:
            video_data: Video data
            
        Returns:
            Learning structure
        """
        structure = {
            'learning_objectives': [],
            'topics_covered': [],
            'estimated_completion_time': video_data.get('duration', 0),
            'difficulty_level': 'intermediate',  # Default
            'prerequisites': [],
            'key_concepts': [],
        }
        
        # Extract from title and description
        title = video_data.get('title', '')
        description = video_data.get('description', '')
        
        # Simple extraction of topics (would use NLP in production)
        if 'beginner' in title.lower() or 'introduction' in title.lower():
            structure['difficulty_level'] = 'beginner'
        elif 'advanced' in title.lower() or 'expert' in title.lower():
            structure['difficulty_level'] = 'advanced'
        
        # Extract topics from chapters
        chapters = video_data.get('chapters', [])
        if chapters:
            structure['topics_covered'] = [
                chapter['title'] for chapter in chapters
            ]
        
        # Extract learning objectives from description
        objective_patterns = [
            r'you will learn:?\s*([^.]+)',
            r'this video covers:?\s*([^.]+)',
            r'topics include:?\s*([^.]+)',
        ]
        
        for pattern in objective_patterns:
            matches = re.findall(pattern, description.lower())
            structure['learning_objectives'].extend(matches)
        
        return structure
    
    async def extract_video_series(
        self,
        playlist_url: str
    ) -> List[Dict[str, Any]]:
        """
        Extract all videos from a playlist or series.
        
        Args:
            playlist_url: URL of playlist
            
        Returns:
            List of video data
        """
        logger.info(f"Extracting video series from: {playlist_url}")
        
        try:
            # Configure for playlist extraction
            playlist_opts = self.ydl_opts.copy()
            playlist_opts['extract_flat'] = True
            
            with yt_dlp.YoutubeDL(playlist_opts) as ydl:
                playlist_info = await asyncio.to_thread(
                    ydl.extract_info, playlist_url, download=False
                )
            
            if not playlist_info or 'entries' not in playlist_info:
                return []
            
            videos = []
            for i, entry in enumerate(playlist_info['entries']):
                if entry:
                    video_data = {
                        'id': entry.get('id', ''),
                        'url': entry.get('url', ''),
                        'title': entry.get('title', ''),
                        'index_in_series': i + 1,
                        'series_title': playlist_info.get('title', ''),
                        'series_id': playlist_info.get('id', ''),
                        'type': 'video_series_item',
                    }
                    videos.append(video_data)
            
            logger.info(f"Found {len(videos)} videos in series")
            return videos
            
        except Exception as e:
            logger.error(f"Failed to extract video series: {e}")
            return []