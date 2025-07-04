import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from ..config.settings import settings_manager
from ..utils.logger import get_logger
from ..utils.checkpoint_manager import CheckpointManager
from ..utils.validation import validate_bookmark_data
from ..analyzers.content_analyzer import ContentAnalyzer
from ..analyzers.categorizer import Categorizer
from ..analyzers.tagger import Tagger
from ..extractors.tweet_extractor import TweetExtractor
from ..extractors.thread_extractor import ThreadExtractor
from ..extractors.video_extractor import VideoExtractor


@dataclass
class BookmarkData:
    id: str
    url: str
    title: str
    content: str
    author: str
    created_at: datetime
    bookmark_type: str
    metadata: Dict[str, Any]
    raw_data: Dict[str, Any]


@dataclass
class ProcessedBookmark:
    bookmark_data: BookmarkData
    analysis_results: Dict[str, Any]
    categories: List[str]
    tags: List[str]
    processed_at: datetime
    processing_time: float


class BookmarkProcessor:
    def __init__(self, 
                 progress_callback: Optional[Callable[[int, int], None]] = None,
                 error_callback: Optional[Callable[[Exception, Dict[str, Any]], None]] = None):
        self.settings = settings_manager.settings
        self.logger = get_logger(__name__)
        self.checkpoint_manager = CheckpointManager(self.settings.processing.checkpoint_dir)
        self.progress_callback = progress_callback
        self.error_callback = error_callback
        
        # Initialize analyzers
        self.content_analyzer = ContentAnalyzer()
        self.categorizer = Categorizer()
        self.tagger = Tagger()
        
        # Initialize extractors
        self.extractors = {
            'tweet': TweetExtractor(),
            'thread': ThreadExtractor(),
            'video': VideoExtractor()
        }
        
        # Processing statistics
        self.stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': None,
            'end_time': None
        }
    
    async def process_bookmarks(self, 
                              bookmarks: List[Dict[str, Any]], 
                              checkpoint_key: str = "bookmark_processing") -> List[ProcessedBookmark]:
        self.stats['start_time'] = datetime.now()
        self.stats['total_processed'] = 0
        
        try:
            # Load checkpoint if exists
            checkpoint_data = self.checkpoint_manager.load_checkpoint(checkpoint_key)
            processed_ids = set(checkpoint_data.get('processed_ids', []))
            
            results = []
            batch_size = self.settings.processing.batch_size
            
            for i in range(0, len(bookmarks), batch_size):
                batch = bookmarks[i:i + batch_size]
                batch_results = await self._process_batch(batch, processed_ids)
                results.extend(batch_results)
                
                # Update checkpoint
                processed_ids.update([result.bookmark_data.id for result in batch_results])
                if i % self.settings.processing.checkpoint_interval == 0:
                    await self._save_checkpoint(checkpoint_key, processed_ids, results)
                
                # Report progress
                if self.progress_callback:
                    self.progress_callback(i + len(batch), len(bookmarks))
            
            # Final checkpoint save
            await self._save_checkpoint(checkpoint_key, processed_ids, results)
            
            self.stats['end_time'] = datetime.now()
            self._log_processing_stats()
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error processing bookmarks: {str(e)}")
            if self.error_callback:
                self.error_callback(e, {'checkpoint_key': checkpoint_key})
            raise
    
    async def _process_batch(self, 
                           batch: List[Dict[str, Any]], 
                           processed_ids: set) -> List[ProcessedBookmark]:
        tasks = []
        for bookmark_data in batch:
            if bookmark_data.get('id') not in processed_ids:
                tasks.append(self._process_single_bookmark(bookmark_data))
        
        if not tasks:
            return []
        
        # Process batch concurrently
        semaphore = asyncio.Semaphore(self.settings.processing.max_workers)
        batch_results = await asyncio.gather(
            *[self._process_with_semaphore(semaphore, task) for task in tasks],
            return_exceptions=True
        )
        
        # Filter out exceptions and log errors
        valid_results = []
        for result in batch_results:
            if isinstance(result, Exception):
                self.stats['failed'] += 1
                self.logger.error(f"Error processing bookmark: {str(result)}")
                if self.error_callback:
                    self.error_callback(result, {})
            else:
                valid_results.append(result)
                self.stats['successful'] += 1
        
        return valid_results
    
    async def _process_with_semaphore(self, semaphore: asyncio.Semaphore, coro):
        async with semaphore:
            return await coro
    
    async def _process_single_bookmark(self, bookmark_data: Dict[str, Any]) -> ProcessedBookmark:
        start_time = datetime.now()
        
        try:
            # Validate bookmark data
            if not validate_bookmark_data(bookmark_data):
                self.stats['skipped'] += 1
                raise ValueError("Invalid bookmark data")
            
            # Extract content based on bookmark type
            bookmark_type = self._determine_bookmark_type(bookmark_data['url'])
            extracted_data = await self._extract_content(bookmark_data, bookmark_type)
            
            # Create BookmarkData object
            bookmark_obj = BookmarkData(
                id=bookmark_data['id'],
                url=bookmark_data['url'],
                title=extracted_data.get('title', ''),
                content=extracted_data.get('content', ''),
                author=extracted_data.get('author', ''),
                created_at=datetime.fromisoformat(bookmark_data.get('created_at', datetime.now().isoformat())),
                bookmark_type=bookmark_type,
                metadata=extracted_data.get('metadata', {}),
                raw_data=bookmark_data
            )
            
            # Analyze content
            analysis_results = {}
            if self.settings.analysis.enable_content_analysis:
                analysis_results['content_analysis'] = await self.content_analyzer.analyze(bookmark_obj.content)
            
            # Categorize content
            categories = []
            if self.settings.analysis.enable_categorization:
                categories = await self.categorizer.categorize(bookmark_obj.content)
            
            # Generate tags
            tags = []
            if self.settings.analysis.enable_tagging:
                tags = await self.tagger.generate_tags(bookmark_obj.content)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return ProcessedBookmark(
                bookmark_data=bookmark_obj,
                analysis_results=analysis_results,
                categories=categories,
                tags=tags,
                processed_at=datetime.now(),
                processing_time=processing_time
            )
            
        except Exception as e:
            self.logger.error(f"Error processing bookmark {bookmark_data.get('id', 'unknown')}: {str(e)}")
            raise
    
    def _determine_bookmark_type(self, url: str) -> str:
        if 'twitter.com' in url or 'x.com' in url:
            if '/status/' in url:
                return 'tweet'
            elif '/thread/' in url:
                return 'thread'
        elif 'youtube.com' in url or 'youtu.be' in url:
            return 'video'
        else:
            return 'general'
    
    async def _extract_content(self, bookmark_data: Dict[str, Any], bookmark_type: str) -> Dict[str, Any]:
        extractor = self.extractors.get(bookmark_type)
        if extractor:
            return await extractor.extract(bookmark_data)
        else:
            # Default extraction for general content
            return {
                'title': bookmark_data.get('title', ''),
                'content': bookmark_data.get('content', ''),
                'author': bookmark_data.get('author', ''),
                'metadata': {}
            }
    
    async def _save_checkpoint(self, checkpoint_key: str, processed_ids: set, results: List[ProcessedBookmark]):
        checkpoint_data = {
            'processed_ids': list(processed_ids),
            'results_count': len(results),
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats
        }
        self.checkpoint_manager.save_checkpoint(checkpoint_key, checkpoint_data)
    
    def _log_processing_stats(self):
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        self.logger.info(f"Processing completed in {duration:.2f}s")
        self.logger.info(f"Total processed: {self.stats['total_processed']}")
        self.logger.info(f"Successful: {self.stats['successful']}")
        self.logger.info(f"Failed: {self.stats['failed']}")
        self.logger.info(f"Skipped: {self.stats['skipped']}")
    
    def get_processing_stats(self) -> Dict[str, Any]:
        return self.stats.copy()
    
    def export_results(self, results: List[ProcessedBookmark], format: str = "json") -> str:
        if format == "json":
            return json.dumps([asdict(result) for result in results], indent=2, default=str)
        elif format == "csv":
            # TODO: Implement CSV export
            raise NotImplementedError("CSV export not yet implemented")
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def clear_checkpoints(self, checkpoint_key: str = "bookmark_processing"):
        self.checkpoint_manager.clear_checkpoint(checkpoint_key)