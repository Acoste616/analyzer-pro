"""Content extraction orchestration module."""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from ..extractors import TweetExtractor, ThreadExtractor, VideoExtractor
from ..utils.logger import get_logger, log_execution_time, ProgressLogger
from ..utils.checkpoint_manager import CheckpointManager
from ..config import get_settings

logger = get_logger(__name__)


class ContentExtractor:
    """Orchestrate content extraction from various sources."""
    
    def __init__(
        self,
        checkpoint_manager: Optional[CheckpointManager] = None,
        enable_video_extraction: bool = True,
        enable_thread_reconstruction: bool = True
    ):
        """
        Initialize content extractor.
        
        Args:
            checkpoint_manager: Checkpoint manager for resumable processing
            enable_video_extraction: Whether to extract video content
            enable_thread_reconstruction: Whether to reconstruct threads
        """
        self.settings = get_settings()
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self.enable_video_extraction = enable_video_extraction
        self.enable_thread_reconstruction = enable_thread_reconstruction
        
        # Initialize extractors
        self.tweet_extractor = TweetExtractor()
        self.thread_extractor = ThreadExtractor() if enable_thread_reconstruction else None
        self.video_extractor = VideoExtractor() if enable_video_extraction else None
        
    @log_execution_time
    async def extract_all_content(
        self,
        input_path: Path,
        input_format: str = "auto",
        resume_from_checkpoint: bool = True
    ) -> Dict[str, Any]:
        """
        Extract all content from input file.
        
        Args:
            input_path: Path to input file (CSV or JSON)
            input_format: Input format (csv, json, auto)
            resume_from_checkpoint: Whether to resume from checkpoint
            
        Returns:
            Extraction results
        """
        logger.info(f"Starting content extraction from: {input_path}")
        
        # Determine input format
        if input_format == "auto":
            input_format = self._detect_input_format(input_path)
        
        # Initialize or resume checkpoint
        checkpoint_id = f"extraction_{input_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if resume_from_checkpoint:
            latest_checkpoint = self.checkpoint_manager.get_latest_checkpoint()
            if latest_checkpoint and not latest_checkpoint.is_complete:
                logger.info(f"Resuming from checkpoint: {latest_checkpoint.checkpoint_id}")
                checkpoint_id = latest_checkpoint.checkpoint_id
        
        # Extract initial content
        async with self.tweet_extractor as extractor:
            if input_format == "csv":
                all_content = await extractor.extract_from_csv(input_path)
            elif input_format == "json":
                all_content = await extractor.extract_from_json(input_path)
            else:
                raise ValueError(f"Unsupported input format: {input_format}")
        
        logger.info(f"Extracted {len(all_content)} initial content items")
        
        # Create checkpoint
        if not self.checkpoint_manager.current_checkpoint:
            self.checkpoint_manager.create_checkpoint(
                checkpoint_id,
                total_items=len(all_content),
                initial_data={'input_path': str(input_path), 'input_format': input_format}
            )
        
        # Process content in stages
        results = await self._process_content_stages(all_content)
        
        # Mark checkpoint as complete
        self.checkpoint_manager.update_checkpoint(
            processed_items=len(all_content),
            data_update={'results': results}
        )
        if self.checkpoint_manager.current_checkpoint:
            self.checkpoint_manager.current_checkpoint.status = "completed"
        
        logger.info("Content extraction completed successfully")
        return results
    
    async def _process_content_stages(self, all_content: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process content through various extraction stages."""
        results = {
            'tweets': [],
            'threads': [],
            'videos': [],
            'standalone_tweets': [],
            'statistics': {},
            'extraction_metadata': {
                'start_time': datetime.now().isoformat(),
                'extractors_used': []
            }
        }
        
        # Stage 1: Separate content types
        tweets = []
        potential_videos = []
        
        with ProgressLogger(len(all_content), "Categorizing content") as progress:
            for item in all_content:
                content_type = self._identify_content_type(item)
                
                if content_type == 'video':
                    potential_videos.append(item)
                else:
                    tweets.append(item)
                
                progress.update()
        
        results['extraction_metadata']['extractors_used'].append('tweet_extractor')
        
        # Stage 2: Extract threads if enabled
        if self.enable_thread_reconstruction and self.thread_extractor and tweets:
            logger.info(f"Reconstructing threads from {len(tweets)} tweets")
            threads, standalone = await self.thread_extractor.extract_threads(tweets)
            
            results['threads'] = threads
            results['standalone_tweets'] = standalone
            results['extraction_metadata']['extractors_used'].append('thread_extractor')
            
            logger.info(f"Found {len(threads)} threads and {len(standalone)} standalone tweets")
        else:
            results['standalone_tweets'] = tweets
        
        # Stage 3: Extract video content if enabled
        if self.enable_video_extraction and self.video_extractor and potential_videos:
            logger.info(f"Extracting video content from {len(potential_videos)} items")
            
            async with self.video_extractor as extractor:
                videos = await extractor.extract_from_bookmarks(potential_videos)
            
            results['videos'] = videos
            results['extraction_metadata']['extractors_used'].append('video_extractor')
            
            logger.info(f"Successfully extracted {len(videos)} videos")
        
        # Calculate statistics
        results['statistics'] = self._calculate_extraction_statistics(results)
        results['extraction_metadata']['end_time'] = datetime.now().isoformat()
        
        return results
    
    def _detect_input_format(self, input_path: Path) -> str:
        """Detect input file format based on extension."""
        extension = input_path.suffix.lower()
        
        if extension == '.csv':
            return 'csv'
        elif extension in ['.json', '.jsonl']:
            return 'json'
        else:
            # Try to detect from content
            with open(input_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line.startswith('{') or first_line.startswith('['):
                    return 'json'
                elif ',' in first_line:
                    return 'csv'
        
        raise ValueError(f"Cannot detect input format for: {input_path}")
    
    def _identify_content_type(self, item: Dict[str, Any]) -> str:
        """Identify the type of content."""
        url = item.get('url', '')
        content = item.get('content', '').lower()
        
        # Check for video indicators
        video_domains = ['youtube.com', 'youtu.be', 'vimeo.com', 'udemy.com']
        if any(domain in url for domain in video_domains):
            return 'video'
        
        if any(word in content for word in ['video', 'watch', 'course', 'tutorial video']):
            return 'video'
        
        # Default to tweet
        return 'tweet'
    
    def _calculate_extraction_statistics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate extraction statistics."""
        stats = {
            'total_items': (
                len(results.get('standalone_tweets', [])) +
                len(results.get('threads', [])) +
                len(results.get('videos', []))
            ),
            'content_types': {
                'tweets': len(results.get('standalone_tweets', [])),
                'threads': len(results.get('threads', [])),
                'videos': len(results.get('videos', []))
            },
            'thread_statistics': {},
            'video_statistics': {}
        }
        
        # Thread statistics
        if results.get('threads'):
            thread_lengths = [thread.get('tweet_count', 0) for thread in results['threads']]
            stats['thread_statistics'] = {
                'total_threads': len(results['threads']),
                'total_tweets_in_threads': sum(thread_lengths),
                'average_thread_length': sum(thread_lengths) / len(thread_lengths) if thread_lengths else 0,
                'longest_thread': max(thread_lengths) if thread_lengths else 0,
                'shortest_thread': min(thread_lengths) if thread_lengths else 0
            }
        
        # Video statistics
        if results.get('videos'):
            video_durations = [video.get('duration', 0) for video in results['videos']]
            stats['video_statistics'] = {
                'total_videos': len(results['videos']),
                'total_duration_seconds': sum(video_durations),
                'average_duration_seconds': sum(video_durations) / len(video_durations) if video_durations else 0,
                'videos_with_transcripts': sum(
                    1 for video in results['videos']
                    if video.get('metadata', {}).get('has_transcript')
                ),
                'educational_videos': sum(
                    1 for video in results['videos']
                    if video.get('metadata', {}).get('is_educational')
                )
            }
        
        return stats
    
    async def extract_specific_content(
        self,
        content_items: List[Dict[str, Any]],
        content_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Extract specific types of content.
        
        Args:
            content_items: List of content items
            content_types: Types to extract (tweets, threads, videos)
            
        Returns:
            Extraction results
        """
        if content_types is None:
            content_types = ['tweets', 'threads', 'videos']
        
        results = {
            'tweets': [],
            'threads': [],
            'videos': [],
            'standalone_tweets': []
        }
        
        # Filter content by type
        tweets = []
        videos = []
        
        for item in content_items:
            content_type = self._identify_content_type(item)
            if content_type == 'video' and 'videos' in content_types:
                videos.append(item)
            elif content_type == 'tweet' and ('tweets' in content_types or 'threads' in content_types):
                tweets.append(item)
        
        # Extract threads
        if 'threads' in content_types and self.thread_extractor and tweets:
            threads, standalone = await self.thread_extractor.extract_threads(tweets)
            results['threads'] = threads
            results['standalone_tweets'] = standalone
        elif 'tweets' in content_types:
            results['standalone_tweets'] = tweets
        
        # Extract videos
        if 'videos' in content_types and self.video_extractor and videos:
            async with self.video_extractor as extractor:
                results['videos'] = await extractor.extract_from_bookmarks(videos)
        
        return results
    
    def merge_extraction_results(
        self,
        *results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge multiple extraction results.
        
        Args:
            *results: Variable number of extraction results
            
        Returns:
            Merged results
        """
        merged = {
            'tweets': [],
            'threads': [],
            'videos': [],
            'standalone_tweets': [],
            'statistics': {}
        }
        
        for result in results:
            merged['tweets'].extend(result.get('tweets', []))
            merged['threads'].extend(result.get('threads', []))
            merged['videos'].extend(result.get('videos', []))
            merged['standalone_tweets'].extend(result.get('standalone_tweets', []))
        
        # Recalculate statistics
        merged['statistics'] = self._calculate_extraction_statistics(merged)
        
        return merged
    
    def filter_by_date_range(
        self,
        results: Dict[str, Any],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Filter extraction results by date range.
        
        Args:
            results: Extraction results
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Filtered results
        """
        filtered = {
            'tweets': [],
            'threads': [],
            'videos': [],
            'standalone_tweets': []
        }
        
        def is_in_date_range(item: Dict[str, Any]) -> bool:
            created_at = item.get('created_at')
            if not created_at:
                return True
            
            try:
                # Parse date
                if isinstance(created_at, str):
                    item_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                else:
                    item_date = created_at
                
                if start_date and item_date < start_date:
                    return False
                if end_date and item_date > end_date:
                    return False
                
                return True
            except:
                return True
        
        # Filter each content type
        for key in ['tweets', 'threads', 'videos', 'standalone_tweets']:
            if key in results:
                filtered[key] = [
                    item for item in results[key]
                    if is_in_date_range(item)
                ]
        
        # Recalculate statistics
        filtered['statistics'] = self._calculate_extraction_statistics(filtered)
        
        return filtered