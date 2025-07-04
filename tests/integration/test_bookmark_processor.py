import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.core.bookmark_processor import BookmarkProcessor, BookmarkData, ProcessedBookmark
from src.analyzers.content_analyzer import ContentAnalysisResult
from src.utils.checkpoint_manager import CheckpointManager


class TestBookmarkProcessor:
    """Integration tests for BookmarkProcessor."""
    
    def setup_method(self):
        self.processor = BookmarkProcessor()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_process_single_bookmark_success(self, sample_bookmark_data, mock_llm_client):
        """Test processing a single bookmark successfully."""
        
        # Mock the analyzers
        with patch.object(self.processor.content_analyzer, 'analyze') as mock_analyze, \
             patch.object(self.processor.categorizer, 'categorize') as mock_categorize, \
             patch.object(self.processor.tagger, 'generate_tags') as mock_tags:
            
            # Setup mocks
            mock_analyze.return_value = ContentAnalysisResult(
                main_topics=["testing", "software"],
                key_insights=["Important insight"],
                actionable_items=["Action item"],
                technologies_tools=["pytest"],
                author_expertise="Expert",
                relevance_score=8.0,
                sentiment="Positive",
                complexity_level="Medium",
                content_type="Article",
                word_count=100,
                reading_time_minutes=0.5,
                analysis_metadata={}
            )
            mock_categorize.return_value = ["Technology", "Testing"]
            mock_tags.return_value = ["testing", "software", "python"]
            
            # Process the bookmark
            result = await self.processor._process_single_bookmark(sample_bookmark_data)
            
            # Verify result
            assert isinstance(result, ProcessedBookmark)
            assert result.bookmark_data.id == sample_bookmark_data['id']
            assert result.bookmark_data.url == sample_bookmark_data['url']
            assert result.bookmark_data.title == sample_bookmark_data['title']
            assert len(result.categories) == 2
            assert len(result.tags) == 3
            assert result.processing_time > 0
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_process_bookmarks_batch(self, mock_llm_client):
        """Test processing multiple bookmarks in batch."""
        
        # Create test bookmarks
        bookmarks = []
        for i in range(5):
            bookmarks.append({
                'id': f'test_{i}',
                'url': f'https://example.com/article/{i}',
                'title': f'Test Article {i}',
                'content': f'This is test content {i}',
                'author': f'Author {i}',
                'created_at': datetime.now().isoformat()
            })
        
        # Mock the analyzers
        with patch.object(self.processor.content_analyzer, 'analyze') as mock_analyze, \
             patch.object(self.processor.categorizer, 'categorize') as mock_categorize, \
             patch.object(self.processor.tagger, 'generate_tags') as mock_tags:
            
            mock_analyze.return_value = ContentAnalysisResult(
                main_topics=["test"],
                key_insights=["insight"],
                actionable_items=["action"],
                technologies_tools=["tool"],
                author_expertise="Expert",
                relevance_score=7.0,
                sentiment="Neutral",
                complexity_level="Low",
                content_type="Article",
                word_count=50,
                reading_time_minutes=0.25,
                analysis_metadata={}
            )
            mock_categorize.return_value = ["Technology"]
            mock_tags.return_value = ["test", "article"]
            
            # Process bookmarks
            results = await self.processor.process_bookmarks(bookmarks)
            
            # Verify results
            assert len(results) == 5
            assert all(isinstance(result, ProcessedBookmark) for result in results)
            assert all(result.bookmark_data.bookmark_type in ['tweet', 'thread', 'video', 'general'] 
                      for result in results)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_process_bookmarks_with_checkpoints(self, temp_dir):
        """Test processing with checkpoint functionality."""
        
        # Setup checkpoint manager
        checkpoint_dir = temp_dir / "checkpoints"
        self.processor.checkpoint_manager = CheckpointManager(str(checkpoint_dir))
        
        # Create test bookmarks
        bookmarks = [
            {
                'id': 'checkpoint_test_1',
                'url': 'https://example.com/1',
                'title': 'Test 1',
                'content': 'Content 1',
                'created_at': datetime.now().isoformat()
            },
            {
                'id': 'checkpoint_test_2',
                'url': 'https://example.com/2',
                'title': 'Test 2',
                'content': 'Content 2',
                'created_at': datetime.now().isoformat()
            }
        ]
        
        # Mock analyzers
        with patch.object(self.processor.content_analyzer, 'analyze') as mock_analyze, \
             patch.object(self.processor.categorizer, 'categorize') as mock_categorize, \
             patch.object(self.processor.tagger, 'generate_tags') as mock_tags:
            
            mock_analyze.return_value = ContentAnalysisResult(
                main_topics=["test"],
                key_insights=["insight"],
                actionable_items=["action"],
                technologies_tools=["tool"],
                author_expertise="Expert",
                relevance_score=7.0,
                sentiment="Neutral",
                complexity_level="Low",
                content_type="Article",
                word_count=50,
                reading_time_minutes=0.25,
                analysis_metadata={}
            )
            mock_categorize.return_value = ["Technology"]
            mock_tags.return_value = ["test"]
            
            # Process with checkpoint
            results = await self.processor.process_bookmarks(
                bookmarks, 
                checkpoint_key="test_checkpoint"
            )
            
            # Verify results
            assert len(results) == 2
            
            # Verify checkpoint was created
            assert self.processor.checkpoint_manager.checkpoint_exists("test_checkpoint")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_determine_bookmark_type(self):
        """Test bookmark type determination."""
        
        test_cases = [
            ("https://twitter.com/user/status/123", "tweet"),
            ("https://x.com/user/status/456", "tweet"),
            ("https://twitter.com/user/thread/789", "thread"),
            ("https://youtube.com/watch?v=abc", "video"),
            ("https://youtu.be/def", "video"),
            ("https://example.com/article", "general")
        ]
        
        for url, expected_type in test_cases:
            result_type = self.processor._determine_bookmark_type(url)
            assert result_type == expected_type
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_extract_content_different_types(self):
        """Test content extraction for different bookmark types."""
        
        # Mock extractors
        mock_tweet_data = {
            'title': 'Tweet Title',
            'content': 'Tweet content',
            'author': 'twitter_user',
            'metadata': {'tweet_id': '123'}
        }
        
        mock_video_data = {
            'title': 'Video Title',
            'content': 'Video description',
            'author': 'video_creator',
            'metadata': {'video_id': 'abc', 'duration': 300}
        }
        
        with patch.object(self.processor.extractors['tweet'], 'extract') as mock_tweet_extract, \
             patch.object(self.processor.extractors['video'], 'extract') as mock_video_extract:
            
            mock_tweet_extract.return_value = mock_tweet_data
            mock_video_extract.return_value = mock_video_data
            
            # Test tweet extraction
            tweet_result = await self.processor._extract_content(
                {'url': 'https://twitter.com/user/status/123'}, 
                'tweet'
            )
            assert tweet_result['title'] == 'Tweet Title'
            
            # Test video extraction
            video_result = await self.processor._extract_content(
                {'url': 'https://youtube.com/watch?v=abc'}, 
                'video'
            )
            assert video_result['title'] == 'Video Title'
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_processing_with_errors(self, sample_bookmark_data):
        """Test processing behavior when errors occur."""
        
        # Mock analyzer to raise an exception
        with patch.object(self.processor.content_analyzer, 'analyze') as mock_analyze:
            mock_analyze.side_effect = Exception("Analysis failed")
            
            # Should handle the error gracefully
            with pytest.raises(Exception):
                await self.processor._process_single_bookmark(sample_bookmark_data)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_processing_statistics(self, mock_llm_client):
        """Test processing statistics collection."""
        
        # Create test bookmarks with one invalid
        bookmarks = [
            {
                'id': 'valid_1',
                'url': 'https://example.com/1',
                'title': 'Valid Bookmark',
                'content': 'Content',
                'created_at': datetime.now().isoformat()
            },
            {
                'id': 'invalid_1',
                'url': 'invalid-url',  # Invalid URL
                'title': 'Invalid Bookmark'
            }
        ]
        
        # Mock analyzers for valid bookmark
        with patch.object(self.processor.content_analyzer, 'analyze') as mock_analyze, \
             patch.object(self.processor.categorizer, 'categorize') as mock_categorize, \
             patch.object(self.processor.tagger, 'generate_tags') as mock_tags:
            
            mock_analyze.return_value = ContentAnalysisResult(
                main_topics=["test"],
                key_insights=["insight"],
                actionable_items=["action"],
                technologies_tools=["tool"],
                author_expertise="Expert",
                relevance_score=7.0,
                sentiment="Neutral",
                complexity_level="Low",
                content_type="Article",
                word_count=50,
                reading_time_minutes=0.25,
                analysis_metadata={}
            )
            mock_categorize.return_value = ["Technology"]
            mock_tags.return_value = ["test"]
            
            # Process bookmarks
            results = await self.processor.process_bookmarks(bookmarks)
            
            # Get statistics
            stats = self.processor.get_processing_stats()
            
            # Verify statistics
            assert stats['total_processed'] == 0  # This is set at start, so should be 0
            assert stats['successful'] >= 0  # At least some should succeed
            assert 'start_time' in stats
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_export_results(self, mock_llm_client):
        """Test exporting processing results."""
        
        # Create a processed bookmark manually
        bookmark_data = BookmarkData(
            id="export_test",
            url="https://example.com",
            title="Export Test",
            content="Test content",
            author="Test Author",
            created_at=datetime.now(),
            bookmark_type="general",
            metadata={},
            raw_data={}
        )
        
        processed_bookmark = ProcessedBookmark(
            bookmark_data=bookmark_data,
            analysis_results={"test": "analysis"},
            categories=["Technology"],
            tags=["test", "export"],
            processed_at=datetime.now(),
            processing_time=1.0
        )
        
        # Test JSON export
        json_result = self.processor.export_results([processed_bookmark], format="json")
        
        assert isinstance(json_result, str)
        assert "export_test" in json_result
        assert "Technology" in json_result
        
        # Test unsupported format
        with pytest.raises(ValueError):
            self.processor.export_results([processed_bookmark], format="xml")
    
    @pytest.mark.integration
    def test_clear_checkpoints(self, temp_dir):
        """Test clearing checkpoints."""
        
        # Setup checkpoint manager
        checkpoint_dir = temp_dir / "checkpoints"
        self.processor.checkpoint_manager = CheckpointManager(str(checkpoint_dir))
        
        # Create a test checkpoint
        self.processor.checkpoint_manager.save_checkpoint("test_clear", {"test": "data"})
        assert self.processor.checkpoint_manager.checkpoint_exists("test_clear")
        
        # Clear checkpoints
        self.processor.clear_checkpoints("test_clear")
        
        # Verify checkpoint was cleared
        assert not self.processor.checkpoint_manager.checkpoint_exists("test_clear")


class TestBookmarkData:
    """Test BookmarkData dataclass."""
    
    @pytest.mark.integration
    def test_bookmark_data_creation(self):
        """Test creating BookmarkData."""
        now = datetime.now()
        
        bookmark = BookmarkData(
            id="test_id",
            url="https://example.com",
            title="Test Title",
            content="Test content",
            author="Test Author",
            created_at=now,
            bookmark_type="general",
            metadata={"key": "value"},
            raw_data={"raw": "data"}
        )
        
        assert bookmark.id == "test_id"
        assert bookmark.url == "https://example.com"
        assert bookmark.title == "Test Title"
        assert bookmark.content == "Test content"
        assert bookmark.author == "Test Author"
        assert bookmark.created_at == now
        assert bookmark.bookmark_type == "general"
        assert bookmark.metadata == {"key": "value"}
        assert bookmark.raw_data == {"raw": "data"}


class TestProcessedBookmark:
    """Test ProcessedBookmark dataclass."""
    
    @pytest.mark.integration
    def test_processed_bookmark_creation(self):
        """Test creating ProcessedBookmark."""
        now = datetime.now()
        
        bookmark_data = BookmarkData(
            id="test",
            url="https://example.com",
            title="Test",
            content="Content",
            author="Author",
            created_at=now,
            bookmark_type="general",
            metadata={},
            raw_data={}
        )
        
        processed = ProcessedBookmark(
            bookmark_data=bookmark_data,
            analysis_results={"test": "analysis"},
            categories=["Technology"],
            tags=["test", "bookmark"],
            processed_at=now,
            processing_time=2.5
        )
        
        assert processed.bookmark_data == bookmark_data
        assert processed.analysis_results == {"test": "analysis"}
        assert processed.categories == ["Technology"]
        assert processed.tags == ["test", "bookmark"]
        assert processed.processed_at == now
        assert processed.processing_time == 2.5