import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.extractors.tweet_extractor import TweetExtractor


class TestTweetExtractor:
    """Test TweetExtractor class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        with patch('src.extractors.tweet_extractor.settings_manager') as mock_settings:
            mock_settings.settings.extractors = {
                'twitter': {
                    'base_url': 'https://api.twitter.com/2',
                    'timeout': 30,
                    'rate_limit': {'requests_per_minute': 300}
                }
            }
            self.extractor = TweetExtractor()
    
    @pytest.mark.unit
    def test_is_twitter_url_valid(self):
        """Test valid Twitter URLs."""
        valid_urls = [
            "https://twitter.com/user/status/123456789",
            "https://x.com/user/status/123456789",
            "https://www.twitter.com/user/status/123456789",
            "https://www.x.com/user/status/123456789"
        ]
        
        for url in valid_urls:
            assert self.extractor._is_twitter_url(url) is True
    
    @pytest.mark.unit
    def test_is_twitter_url_invalid(self):
        """Test invalid Twitter URLs."""
        invalid_urls = [
            "https://facebook.com/user/status/123456789",
            "https://youtube.com/watch?v=123456789",
            "https://example.com/user/status/123456789",
            "not-a-url"
        ]
        
        for url in invalid_urls:
            assert self.extractor._is_twitter_url(url) is False
    
    @pytest.mark.unit
    def test_extract_tweet_id(self):
        """Test tweet ID extraction."""
        test_cases = [
            ("https://twitter.com/user/status/123456789", "123456789"),
            ("https://x.com/user/status/987654321", "987654321"),
            ("https://twitter.com/user/status/123456789?ref_src=twsrc", "123456789"),
            ("https://twitter.com/user/status/", None),
            ("https://twitter.com/user/", None),
            ("invalid-url", None)
        ]
        
        for url, expected_id in test_cases:
            result = self.extractor._extract_tweet_id(url)
            assert result == expected_id
    
    @pytest.mark.unit
    def test_extract_title(self):
        """Test title extraction from HTML."""
        html_samples = [
            '<title>Test Tweet / X</title>',
            '<meta property="og:title" content="Test Tweet Content">',
            '<meta name="twitter:title" content="Another Test Tweet">',
            '<title>User on X: "This is a test tweet"</title>'
        ]
        
        expected_titles = [
            "Test Tweet",
            "Test Tweet Content",
            "Another Test Tweet",
            'User on X: "This is a test tweet"'
        ]
        
        for html, expected in zip(html_samples, expected_titles):
            result = self.extractor._extract_title(html)
            assert result == expected
    
    @pytest.mark.unit
    def test_extract_content(self):
        """Test content extraction from HTML."""
        html_samples = [
            '<div data-testid="tweetText">This is a test tweet</div>',
            '<div class="tweet-text">Another test tweet</div>',
            '<p class="tweet-text">Yet another tweet</p>',
            '<meta property="og:description" content="Meta description tweet">',
            '<meta name="twitter:description" content="Twitter description tweet">'
        ]
        
        expected_contents = [
            "This is a test tweet",
            "Another test tweet",
            "Yet another tweet",
            "Meta description tweet",
            "Twitter description tweet"
        ]
        
        for html, expected in zip(html_samples, expected_contents):
            result = self.extractor._extract_content(html)
            assert result == expected
    
    @pytest.mark.unit
    def test_extract_author(self):
        """Test author extraction from HTML."""
        html_samples = [
            '<div data-testid="User-Names"><span>@testuser</span></div>',
            '<a href="https://twitter.com/testuser">@testuser</a>',
            '<meta name="twitter:creator" content="@testuser">',
            '<meta property="twitter:creator" content="@testuser">'
        ]
        
        for html in html_samples:
            result = self.extractor._extract_author(html)
            assert result == "testuser"
    
    @pytest.mark.unit
    def test_extract_published_date(self):
        """Test published date extraction from HTML."""
        html_samples = [
            '<time datetime="2024-01-01T12:00:00Z">Jan 1</time>',
            '<meta property="article:published_time" content="2024-01-01T12:00:00Z">',
            '<time datetime="2024-01-01T12:00:00+00:00">Jan 1</time>'
        ]
        
        for html in html_samples:
            result = self.extractor._extract_published_date(html)
            assert result is not None
            assert isinstance(result, datetime)
    
    @pytest.mark.unit
    def test_extract_metadata_from_html(self):
        """Test metadata extraction from HTML."""
        html = """
        <div data-testid="reply">5</div>
        <div data-testid="retweet">10</div>
        <div data-testid="like">25</div>
        <div>#python #testing @mention</div>
        <img src="https://pbs.twimg.com/media/test.jpg">
        """
        
        metadata = self.extractor._extract_metadata_from_html(html)
        
        assert metadata.get('reply_count') == 5
        assert metadata.get('retweet_count') == 10
        assert metadata.get('like_count') == 25
        assert 'python' in metadata.get('hashtags', [])
        assert 'testing' in metadata.get('hashtags', [])
        assert 'mention' in metadata.get('mentions', [])
        assert len(metadata.get('media_urls', [])) > 0
    
    @pytest.mark.unit
    def test_clean_html(self):
        """Test HTML cleaning."""
        html_samples = [
            '<p>This is a <strong>test</strong> tweet</p>',
            '<div>Tweet with <a href="url">link</a></div>',
            '<span>Tweet&nbsp;&amp;&quot;quoted&quot;</span>',
            '<script>alert("test")</script>Clean text<style>body{}</style>'
        ]
        
        expected_results = [
            "This is a test tweet",
            "Tweet with link",
            'Tweet & "quoted"',
            "Clean text"
        ]
        
        for html, expected in zip(html_samples, expected_results):
            result = self.extractor._clean_html(html)
            assert result == expected
    
    @pytest.mark.unit
    def test_enhance_tweet_data(self):
        """Test tweet data enhancement."""
        data = {
            'title': 'Tweet',
            'content': 'This is a test tweet content',
            'author': 'testuser',
            'metadata': {}
        }
        
        enhanced = self.extractor._enhance_tweet_data(data, '123456789', 'https://twitter.com/user/status/123456789')
        
        assert enhanced['metadata']['tweet_id'] == '123456789'
        assert enhanced['metadata']['original_url'] == 'https://twitter.com/user/status/123456789'
        assert enhanced['metadata']['content_type'] == 'tweet'
        assert enhanced['metadata']['extraction_method'] == 'web_scraping'
        assert 'extracted_at' in enhanced['metadata']
        assert enhanced['title'] != 'Tweet'  # Should be enhanced
    
    @pytest.mark.unit
    def test_get_tweet_metrics(self):
        """Test tweet metrics extraction."""
        data = {
            'metadata': {
                'engagement': {
                    'replies': 5,
                    'retweets': 10,
                    'likes': 25
                }
            }
        }
        
        metrics = self.extractor.get_tweet_metrics(data)
        
        assert metrics['replies'] == 5
        assert metrics['retweets'] == 10
        assert metrics['likes'] == 25
        assert metrics['total_engagement'] == 40
    
    @pytest.mark.unit
    def test_get_tweet_metrics_empty(self):
        """Test tweet metrics extraction with empty data."""
        data = {'metadata': {}}
        
        metrics = self.extractor.get_tweet_metrics(data)
        
        assert metrics['replies'] == 0
        assert metrics['retweets'] == 0
        assert metrics['likes'] == 0
        assert metrics['total_engagement'] == 0
    
    @pytest.mark.unit
    def test_is_retweet(self):
        """Test retweet detection."""
        retweet_data = {'content': 'RT @user: This is a retweet'}
        normal_data = {'content': 'This is a normal tweet'}
        
        assert self.extractor.is_retweet(retweet_data) is True
        assert self.extractor.is_retweet(normal_data) is False
    
    @pytest.mark.unit
    def test_is_reply(self):
        """Test reply detection."""
        reply_data = {'content': '@user This is a reply'}
        normal_data = {'content': 'This is a normal tweet'}
        
        assert self.extractor.is_reply(reply_data) is True
        assert self.extractor.is_reply(normal_data) is False
    
    @pytest.mark.unit
    def test_get_hashtags(self):
        """Test hashtag extraction."""
        data = {
            'content': 'This is a tweet with #python #testing hashtags',
            'metadata': {
                'hashtags': ['python', 'additional']
            }
        }
        
        hashtags = self.extractor.get_hashtags(data)
        
        assert 'python' in hashtags
        assert 'testing' in hashtags
        assert 'additional' in hashtags
        assert len(set(hashtags)) == len(hashtags)  # No duplicates
    
    @pytest.mark.unit
    def test_get_mentions(self):
        """Test mention extraction."""
        data = {
            'content': 'This is a tweet mentioning @user1 and @user2',
            'metadata': {
                'mentions': ['user1', 'additional']
            }
        }
        
        mentions = self.extractor.get_mentions(data)
        
        assert 'user1' in mentions
        assert 'user2' in mentions
        assert 'additional' in mentions
        assert len(set(mentions)) == len(mentions)  # No duplicates
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_extract_invalid_url(self):
        """Test extraction with invalid URL."""
        bookmark_data = {'url': 'invalid-url'}
        
        with pytest.raises(ValueError, match="Invalid URL"):
            await self.extractor.extract(bookmark_data)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_extract_non_twitter_url(self):
        """Test extraction with non-Twitter URL."""
        bookmark_data = {'url': 'https://example.com/page'}
        
        with pytest.raises(ValueError, match="Not a Twitter URL"):
            await self.extractor.extract(bookmark_data)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_extract_no_tweet_id(self):
        """Test extraction with Twitter URL but no tweet ID."""
        bookmark_data = {'url': 'https://twitter.com/user'}
        
        with pytest.raises(ValueError, match="Could not extract tweet ID"):
            await self.extractor.extract(bookmark_data)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_extract_with_web_scraping_error(self):
        """Test extraction when web scraping fails."""
        bookmark_data = {
            'url': 'https://twitter.com/user/status/123456789',
            'content': 'fallback content',
            'author': 'fallback author'
        }
        
        with patch.object(self.extractor, '_extract_from_web_scraping') as mock_web_scraping, \
             patch.object(self.extractor, '_extract_from_oembed') as mock_oembed:
            
            mock_web_scraping.side_effect = Exception("Web scraping failed")
            mock_oembed.side_effect = Exception("oEmbed failed")
            
            result = await self.extractor.extract(bookmark_data)
            
            assert result['title'] == 'Tweet 123456789'
            assert result['content'] == 'fallback content'
            assert result['author'] == 'fallback author'
            assert result['metadata']['tweet_id'] == '123456789'
            assert result['metadata']['extraction_method'] == 'fallback'
            assert 'error' in result['metadata']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        async with self.extractor as extractor:
            assert extractor.session is not None
        
        # Session should be closed after context
        assert self.extractor.session is None or self.extractor.session.closed