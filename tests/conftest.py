import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock
import os

# Test fixtures and configuration


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_bookmark_data():
    """Sample bookmark data for testing."""
    return {
        "id": "test_bookmark_001",
        "url": "https://example.com/article",
        "title": "Test Article",
        "content": "This is a sample article content for testing purposes.",
        "author": "Test Author",
        "created_at": "2024-01-01T12:00:00Z",
        "metadata": {
            "source": "manual",
            "tags": ["test", "sample"]
        }
    }


@pytest.fixture
def sample_tweet_data():
    """Sample tweet data for testing."""
    return {
        "id": "tweet_123456789",
        "url": "https://twitter.com/testuser/status/123456789",
        "title": "Test Tweet",
        "content": "This is a test tweet content #testing @mention",
        "author": "testuser",
        "created_at": "2024-01-01T12:00:00Z",
        "metadata": {
            "tweet_id": "123456789",
            "hashtags": ["testing"],
            "mentions": ["mention"],
            "retweet_count": 5,
            "like_count": 10
        }
    }


@pytest.fixture
def sample_video_data():
    """Sample video data for testing."""
    return {
        "id": "video_987654321",
        "url": "https://youtube.com/watch?v=test123",
        "title": "Test Video Tutorial",
        "content": "Learn how to test software effectively with this comprehensive guide.",
        "author": "TestChannel",
        "created_at": "2024-01-01T12:00:00Z",
        "metadata": {
            "video_id": "test123",
            "platform": "youtube",
            "duration_seconds": 600,
            "view_count": 1000,
            "tags": ["tutorial", "testing", "software"]
        }
    }


@pytest.fixture
def sample_llm_response():
    """Sample LLM response for testing."""
    return {
        "content": "This is a test response from the LLM with analysis results.",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        },
        "model": "test-model-v1",
        "created_at": datetime.now(),
        "processing_time": 1.5,
        "metadata": {
            "provider": "test",
            "temperature": 0.7
        }
    }


@pytest.fixture
def sample_analysis_result():
    """Sample content analysis result for testing."""
    return {
        "main_topics": ["testing", "software development", "quality assurance"],
        "key_insights": [
            "Testing is crucial for software quality",
            "Automated testing saves time and resources",
            "Test-driven development improves code quality"
        ],
        "actionable_items": [
            "Implement automated testing pipeline",
            "Write comprehensive test cases",
            "Set up continuous integration"
        ],
        "technologies_tools": ["pytest", "unittest", "selenium", "jenkins"],
        "author_expertise": "Experienced software developer with testing focus",
        "relevance_score": 8.5,
        "sentiment": "Positive",
        "complexity_level": "Medium",
        "content_type": "Tutorial",
        "word_count": 250,
        "reading_time_minutes": 1.2
    }


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    client = Mock()
    client.generate = AsyncMock()
    client.generate.return_value = Mock(
        content="Test response",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        model="test-model",
        processing_time=1.0,
        metadata={}
    )
    return client


@pytest.fixture
def mock_session():
    """Mock aiohttp session for testing."""
    session = Mock()
    
    # Mock response
    response = Mock()
    response.status = 200
    response.text = AsyncMock(return_value="<html><title>Test Page</title><body>Test content</body></html>")
    response.json = AsyncMock(return_value={"test": "data"})
    
    # Mock context manager
    session.get.return_value.__aenter__ = AsyncMock(return_value=response)
    session.get.return_value.__aexit__ = AsyncMock(return_value=None)
    
    return session


@pytest.fixture
def test_config():
    """Test configuration."""
    return {
        "app": {
            "name": "Test Bookmark Analyzer",
            "version": "1.0.0",
            "environment": "test",
            "debug": True
        },
        "logging": {
            "level": "DEBUG",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": "logs/test.log"
        },
        "database": {
            "type": "sqlite",
            "path": ":memory:"
        },
        "processing": {
            "batch_size": 5,
            "max_workers": 2,
            "checkpoint_interval": 10
        },
        "analysis": {
            "default_llm_provider": "test",
            "enable_content_analysis": True,
            "enable_categorization": True,
            "enable_tagging": True
        }
    }


@pytest.fixture
def test_urls():
    """Collection of test URLs for different platforms."""
    return {
        "valid_https": "https://example.com/article",
        "valid_http": "http://example.com/page",
        "twitter": "https://twitter.com/user/status/123456789",
        "youtube": "https://youtube.com/watch?v=abc123",
        "invalid_scheme": "ftp://example.com/file",
        "invalid_format": "not-a-url",
        "localhost": "http://localhost:8080/test",
        "malformed": "https://",
        "very_long": "https://example.com/" + "a" * 2000
    }


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, temp_dir):
    """Setup test environment with temporary directories."""
    
    # Set test environment variables
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("TEST_MODE", "true")
    
    # Create test directories
    (temp_dir / "logs").mkdir()
    (temp_dir / "data").mkdir()
    (temp_dir / "checkpoints").mkdir()
    
    # Mock file paths
    monkeypatch.setenv("CHECKPOINT_DIR", str(temp_dir / "checkpoints"))
    monkeypatch.setenv("LOG_DIR", str(temp_dir / "logs"))


@pytest.fixture
def mock_file_system(temp_dir):
    """Mock file system with test files."""
    
    # Create test files
    test_file = temp_dir / "test.txt"
    test_file.write_text("Test file content")
    
    json_file = temp_dir / "test.json"
    json_file.write_text('{"test": "data"}')
    
    return {
        "temp_dir": temp_dir,
        "test_file": test_file,
        "json_file": json_file
    }


# Pytest markers for test categorization
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
pytest.mark.external = pytest.mark.external
pytest.mark.llm = pytest.mark.llm
pytest.mark.network = pytest.mark.network
pytest.mark.benchmark = pytest.mark.benchmark


# Skip conditions
skip_if_no_network = pytest.mark.skipif(
    not os.getenv("TEST_NETWORK", False),
    reason="Network tests disabled (set TEST_NETWORK=1 to enable)"
)

skip_if_no_llm_keys = pytest.mark.skipif(
    not any([
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("GEMINI_API_KEY"),
        os.getenv("GROK_API_KEY")
    ]),
    reason="No LLM API keys available"
)

skip_if_slow = pytest.mark.skipif(
    not os.getenv("TEST_SLOW", False),
    reason="Slow tests disabled (set TEST_SLOW=1 to enable)"
)


# Test utilities
class TestDataGenerator:
    """Generate test data for various scenarios."""
    
    @staticmethod
    def generate_bookmarks(count: int = 10):
        """Generate multiple bookmark test data."""
        bookmarks = []
        for i in range(count):
            bookmark = {
                "id": f"test_bookmark_{i:03d}",
                "url": f"https://example.com/article/{i}",
                "title": f"Test Article {i}",
                "content": f"This is test content for article {i}. " * 10,
                "author": f"Author{i}",
                "created_at": f"2024-01-{i+1:02d}T12:00:00Z",
                "metadata": {
                    "source": "test",
                    "index": i
                }
            }
            bookmarks.append(bookmark)
        return bookmarks
    
    @staticmethod
    def generate_invalid_bookmarks(count: int = 5):
        """Generate invalid bookmark test data."""
        invalid_bookmarks = [
            {},  # Empty
            {"id": "test"},  # Missing required fields
            {"id": "", "url": "", "title": ""},  # Empty values
            {"id": "test", "url": "invalid-url", "title": "Test"},  # Invalid URL
            {"id": "test", "url": "https://example.com", "title": "A" * 1000}  # Very long title
        ]
        return invalid_bookmarks[:count]


# Async test helpers
async def async_test_helper(coro, timeout=10):
    """Helper for running async tests with timeout."""
    return await asyncio.wait_for(coro, timeout=timeout)


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "external: marks tests that require external services"
    )
    config.addinivalue_line(
        "markers", "llm: marks tests that require LLM API access"
    )
    config.addinivalue_line(
        "markers", "network: marks tests that require network access"
    )
    config.addinivalue_line(
        "markers", "benchmark: marks tests as performance benchmarks"
    )