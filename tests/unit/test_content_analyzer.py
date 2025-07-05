import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.analyzers.content_analyzer import ContentAnalyzer, ContentAnalysisResult


class TestContentAnalyzer:
    """Test ContentAnalyzer class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        with patch('src.analyzers.content_analyzer.settings_manager') as mock_settings:
            mock_settings.settings.analysis.default_llm_provider = "test"
            mock_settings.llm_configs = {"test": {"test": "config"}}
            mock_settings.get_analysis_prompt.return_value = {
                "user_prompt": "Analyze this content: {content}",
                "system_prompt": "You are a content analyzer."
            }
            
            with patch('src.analyzers.content_analyzer.GrokClient') as mock_grok, \
                 patch('src.analyzers.content_analyzer.ClaudeClient') as mock_claude, \
                 patch('src.analyzers.content_analyzer.GeminiClient') as mock_gemini:
                
                mock_grok.return_value = Mock()
                mock_claude.return_value = Mock()
                mock_gemini.return_value = Mock()
                
                self.analyzer = ContentAnalyzer()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyze_success(self):
        """Test successful content analysis."""
        content = "This is a test article about machine learning and Python programming."
        
        # Mock LLM response
        mock_response = Mock()
        mock_response.content = """
        **Main Topics**
        - Machine Learning
        - Python Programming
        
        **Key Insights**
        - Python is popular for ML
        - Important for data science
        
        **Actionable Items**
        - Learn Python basics
        - Practice ML algorithms
        
        **Technologies/Tools**
        - Python
        - TensorFlow
        
        **Author Expertise**: Expert
        **Relevance Score**: 8.5/10
        """
        mock_response.model = "test-model"
        mock_response.processing_time = 1.5
        mock_response.usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150
        }
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.generate.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        self.analyzer.clients = {"test": mock_client}
        
        result = await self.analyzer.analyze(content)
        
        assert isinstance(result, ContentAnalysisResult)
        assert "Machine Learning" in result.main_topics
        assert "Python Programming" in result.main_topics
        assert "Python is popular for ML" in result.key_insights
        assert "Learn Python basics" in result.actionable_items
        assert "Python" in result.technologies_tools
        assert result.author_expertise == "Expert"
        assert result.relevance_score == 8.5
        assert result.word_count == 11
        assert result.reading_time_minutes > 0
        assert result.analysis_metadata["provider"] == "test"
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyze_empty_content(self):
        """Test analysis with empty content."""
        with pytest.raises(ValueError, match="Content cannot be empty"):
            await self.analyzer.analyze("")
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyze_with_preferred_provider(self):
        """Test analysis with preferred provider."""
        content = "Test content"
        
        mock_response = Mock()
        mock_response.content = "Test analysis"
        mock_response.model = "test-model"
        mock_response.processing_time = 1.0
        mock_response.usage = {"total_tokens": 100}
        
        mock_client = AsyncMock()
        mock_client.generate.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        self.analyzer.clients = {"preferred": mock_client}
        
        result = await self.analyzer.analyze(content, preferred_provider="preferred")
        
        assert result.analysis_metadata["provider"] == "preferred"
    
    @pytest.mark.unit
    def test_extract_sentiment_positive(self):
        """Test sentiment extraction for positive content."""
        text = "This is an excellent and amazing tutorial that's very helpful."
        sentiment = self.analyzer._extract_sentiment(text)
        assert sentiment == "Positive"
    
    @pytest.mark.unit
    def test_extract_sentiment_negative(self):
        """Test sentiment extraction for negative content."""
        text = "This is a terrible and awful tutorial that's completely useless."
        sentiment = self.analyzer._extract_sentiment(text)
        assert sentiment == "Negative"
    
    @pytest.mark.unit
    def test_extract_sentiment_neutral(self):
        """Test sentiment extraction for neutral content."""
        text = "This is a tutorial about programming."
        sentiment = self.analyzer._extract_sentiment(text)
        assert sentiment == "Neutral"
    
    @pytest.mark.unit
    def test_extract_complexity_high(self):
        """Test complexity extraction for high complexity content."""
        text = "This advanced algorithm implementation uses complex architecture."
        complexity = self.analyzer._extract_complexity(text)
        assert complexity == "High"
    
    @pytest.mark.unit
    def test_extract_complexity_low(self):
        """Test complexity extraction for low complexity content."""
        text = "This is a basic and simple introduction for beginners."
        complexity = self.analyzer._extract_complexity(text)
        assert complexity == "Low"
    
    @pytest.mark.unit
    def test_extract_content_type_tutorial(self):
        """Test content type extraction for tutorial."""
        content = "This is a tutorial on how to use Python."
        content_type = self.analyzer._extract_content_type(content)
        assert content_type == "Tutorial"
    
    @pytest.mark.unit
    def test_extract_content_type_review(self):
        """Test content type extraction for review."""
        content = "This is a review and comparison of different frameworks."
        content_type = self.analyzer._extract_content_type(content)
        assert content_type == "Review"
    
    @pytest.mark.unit
    def test_extract_content_type_default(self):
        """Test content type extraction default case."""
        content = "This is some general content."
        content_type = self.analyzer._extract_content_type(content)
        assert content_type == "Article"
    
    @pytest.mark.unit
    def test_extract_topics_fallback(self):
        """Test fallback topic extraction."""
        content = "This article discusses Python programming and machine learning with Docker."
        topics = self.analyzer._extract_topics_fallback(content)
        
        assert "Python" in topics
        assert "Machine Learning" in topics
        assert "Docker" in topics
    
    @pytest.mark.unit
    def test_extract_insights_fallback(self):
        """Test fallback insight extraction."""
        content = "This is important information. The key takeaway is significant. Another crucial point here."
        insights = self.analyzer._extract_insights_fallback(content)
        
        assert len(insights) <= 3
        assert any("important" in insight.lower() for insight in insights)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyze_batch(self):
        """Test batch analysis."""
        contents = ["Content 1", "Content 2", "Content 3"]
        
        mock_response = Mock()
        mock_response.content = "Test analysis"
        mock_response.model = "test-model"
        mock_response.processing_time = 1.0
        mock_response.usage = {"total_tokens": 100}
        
        mock_client = AsyncMock()
        mock_client.generate.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        self.analyzer.clients = {"test": mock_client}
        
        results = await self.analyzer.analyze_batch(contents)
        
        assert len(results) == 3
        assert all(isinstance(result, ContentAnalysisResult) for result in results)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_analyze_batch_with_errors(self):
        """Test batch analysis with some errors."""
        contents = ["Content 1", "Content 2"]
        
        mock_client = AsyncMock()
        # First call succeeds, second fails
        mock_client.generate.side_effect = [
            Mock(content="Success", model="test", processing_time=1.0, usage={"total_tokens": 100}),
            Exception("Analysis failed")
        ]
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        
        self.analyzer.clients = {"test": mock_client}
        
        results = await self.analyzer.analyze_batch(contents)
        
        assert len(results) == 2
        assert results[1].analysis_metadata.get("error") is not None
    
    @pytest.mark.unit
    def test_get_analysis_summary(self):
        """Test analysis summary generation."""
        results = [
            ContentAnalysisResult(
                main_topics=["Python", "AI"],
                key_insights=["Insight 1"],
                actionable_items=["Action 1"],
                technologies_tools=["Tool 1"],
                author_expertise="Expert",
                relevance_score=8.0,
                sentiment="Positive",
                complexity_level="High",
                content_type="Tutorial",
                word_count=100,
                reading_time_minutes=0.5,
                analysis_metadata={}
            ),
            ContentAnalysisResult(
                main_topics=["Python", "Web"],
                key_insights=["Insight 2"],
                actionable_items=["Action 2"],
                technologies_tools=["Tool 2"],
                author_expertise="Intermediate",
                relevance_score=6.0,
                sentiment="Neutral",
                complexity_level="Medium",
                content_type="Article",
                word_count=200,
                reading_time_minutes=1.0,
                analysis_metadata={}
            )
        ]
        
        summary = self.analyzer.get_analysis_summary(results)
        
        assert summary["total_analyzed"] == 2
        assert summary["top_topics"]["Python"] == 2
        assert summary["average_relevance_score"] == 7.0
        assert summary["average_word_count"] == 150
        assert summary["content_type_distribution"]["Tutorial"] == 1
        assert summary["complexity_distribution"]["High"] == 1
    
    @pytest.mark.unit
    def test_get_analysis_summary_empty(self):
        """Test analysis summary with empty results."""
        summary = self.analyzer.get_analysis_summary([])
        assert summary == {}
    
    @pytest.mark.unit
    def test_parse_analysis_response(self):
        """Test parsing of analysis response."""
        response_content = """
        **Main Topics**
        - Topic 1
        - Topic 2
        
        **Key Insights**
        - Insight 1
        - Insight 2
        
        **Author Expertise**: Expert level
        **Relevance Score**: 9.0/10
        """
        
        original_content = "This is test content with multiple words here."
        
        result = self.analyzer._parse_analysis_response(response_content, original_content)
        
        assert "Topic 1" in result.main_topics
        assert "Topic 2" in result.main_topics
        assert "Insight 1" in result.key_insights
        assert "Insight 2" in result.key_insights
        assert result.author_expertise == "Expert level"
        assert result.relevance_score == 9.0
        assert result.word_count == 8


class TestContentAnalysisResult:
    """Test ContentAnalysisResult dataclass."""
    
    @pytest.mark.unit
    def test_content_analysis_result_creation(self):
        """Test creating ContentAnalysisResult."""
        result = ContentAnalysisResult(
            main_topics=["AI", "ML"],
            key_insights=["Insight 1", "Insight 2"],
            actionable_items=["Action 1"],
            technologies_tools=["Python", "TensorFlow"],
            author_expertise="Expert",
            relevance_score=8.5,
            sentiment="Positive",
            complexity_level="High",
            content_type="Tutorial",
            word_count=150,
            reading_time_minutes=0.75,
            analysis_metadata={"provider": "test"}
        )
        
        assert result.main_topics == ["AI", "ML"]
        assert result.key_insights == ["Insight 1", "Insight 2"]
        assert result.actionable_items == ["Action 1"]
        assert result.technologies_tools == ["Python", "TensorFlow"]
        assert result.author_expertise == "Expert"
        assert result.relevance_score == 8.5
        assert result.sentiment == "Positive"
        assert result.complexity_level == "High"
        assert result.content_type == "Tutorial"
        assert result.word_count == 150
        assert result.reading_time_minutes == 0.75
        assert result.analysis_metadata == {"provider": "test"}