import json
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from ..config.settings import settings_manager
from ..utils.logger import get_logger
from ..llm.grok_client import GrokClient
from ..llm.claude_client import ClaudeClient
from ..llm.gemini_client import GeminiClient


@dataclass
class ContentAnalysisResult:
    main_topics: List[str]
    key_insights: List[str]
    actionable_items: List[str]
    technologies_tools: List[str]
    author_expertise: str
    relevance_score: float
    sentiment: str
    complexity_level: str
    content_type: str
    word_count: int
    reading_time_minutes: float
    analysis_metadata: Dict[str, Any]


class ContentAnalyzer:
    def __init__(self):
        self.settings = settings_manager.settings
        self.logger = get_logger(__name__)
        self.llm_configs = settings_manager.llm_configs
        
        # Initialize LLM clients
        self.clients = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize available LLM clients"""
        try:
            self.clients['grok'] = GrokClient()
        except Exception as e:
            self.logger.warning(f"Failed to initialize Grok client: {str(e)}")
        
        try:
            self.clients['claude'] = ClaudeClient()
        except Exception as e:
            self.logger.warning(f"Failed to initialize Claude client: {str(e)}")
        
        try:
            self.clients['gemini'] = GeminiClient()
        except Exception as e:
            self.logger.warning(f"Failed to initialize Gemini client: {str(e)}")
        
        if not self.clients:
            raise ValueError("No LLM clients could be initialized")
    
    async def analyze(self, content: str, preferred_provider: str = None) -> ContentAnalysisResult:
        """
        Analyze content using LLM
        
        Args:
            content: Text content to analyze
            preferred_provider: Preferred LLM provider (grok, claude, gemini)
            
        Returns:
            ContentAnalysisResult object with analysis results
        """
        if not content or not content.strip():
            raise ValueError("Content cannot be empty")
        
        # Choose provider
        provider = preferred_provider or self.settings.analysis.default_llm_provider
        if provider not in self.clients:
            provider = next(iter(self.clients.keys()))
        
        client = self.clients[provider]
        
        # Get analysis prompts
        analysis_prompts = settings_manager.get_analysis_prompt("content_analysis")
        if not analysis_prompts:
            raise ValueError("Content analysis prompts not found in configuration")
        
        # Prepare prompt
        user_prompt = analysis_prompts["user_prompt"].format(content=content)
        system_prompt = analysis_prompts["system_prompt"]
        
        try:
            async with client:
                # Generate structured response
                response = await client.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.3,  # Lower temperature for more consistent analysis
                    max_tokens=2000
                )
                
                # Parse the response
                analysis_result = self._parse_analysis_response(response.content, content)
                
                # Add metadata
                analysis_result.analysis_metadata = {
                    "provider": provider,
                    "model": response.model,
                    "processing_time": response.processing_time,
                    "analyzed_at": datetime.now().isoformat(),
                    "prompt_tokens": response.usage.get("prompt_tokens", 0),
                    "completion_tokens": response.usage.get("completion_tokens", 0),
                    "total_tokens": response.usage.get("total_tokens", 0)
                }
                
                return analysis_result
                
        except Exception as e:
            self.logger.error(f"Error analyzing content with {provider}: {str(e)}")
            raise
    
    def _parse_analysis_response(self, response_content: str, original_content: str) -> ContentAnalysisResult:
        """Parse LLM response into structured analysis result"""
        
        # Initialize default values
        main_topics = []
        key_insights = []
        actionable_items = []
        technologies_tools = []
        author_expertise = "Unknown"
        relevance_score = 5.0
        sentiment = "Neutral"
        complexity_level = "Medium"
        content_type = "Article"
        
        # Calculate basic metrics
        word_count = len(original_content.split())
        reading_time_minutes = word_count / 200  # Average reading speed
        
        try:
            # Try to parse structured response
            lines = response_content.strip().split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Identify sections
                if line.startswith('**Main Topics**') or line.startswith('- **Main Topics**'):
                    current_section = 'main_topics'
                elif line.startswith('**Key Insights**') or line.startswith('- **Key Insights**'):
                    current_section = 'key_insights'
                elif line.startswith('**Actionable Items**') or line.startswith('- **Actionable Items**'):
                    current_section = 'actionable_items'
                elif line.startswith('**Technologies/Tools**') or line.startswith('- **Technologies/Tools**'):
                    current_section = 'technologies_tools'
                elif line.startswith('**Author Expertise**') or line.startswith('- **Author Expertise**'):
                    current_section = 'author_expertise'
                elif line.startswith('**Relevance Score**') or line.startswith('- **Relevance Score**'):
                    current_section = 'relevance_score'
                elif line.startswith('- ') and current_section:
                    # Extract list item
                    item = line[2:].strip()
                    if current_section == 'main_topics':
                        main_topics.append(item)
                    elif current_section == 'key_insights':
                        key_insights.append(item)
                    elif current_section == 'actionable_items':
                        actionable_items.append(item)
                    elif current_section == 'technologies_tools':
                        technologies_tools.append(item)
                elif ':' in line and current_section:
                    # Extract value after colon
                    value = line.split(':', 1)[1].strip()
                    if current_section == 'author_expertise':
                        author_expertise = value
                    elif current_section == 'relevance_score':
                        try:
                            relevance_score = float(value.split('/')[0])
                        except:
                            relevance_score = 5.0
            
            # Extract additional insights from unstructured text
            sentiment = self._extract_sentiment(response_content)
            complexity_level = self._extract_complexity(response_content)
            content_type = self._extract_content_type(original_content)
            
        except Exception as e:
            self.logger.warning(f"Error parsing analysis response: {str(e)}")
            # Use fallback analysis
            main_topics = self._extract_topics_fallback(original_content)
            key_insights = self._extract_insights_fallback(original_content)
        
        return ContentAnalysisResult(
            main_topics=main_topics[:10],  # Limit to top 10
            key_insights=key_insights[:10],
            actionable_items=actionable_items[:10],
            technologies_tools=technologies_tools[:15],
            author_expertise=author_expertise,
            relevance_score=max(1.0, min(10.0, relevance_score)),
            sentiment=sentiment,
            complexity_level=complexity_level,
            content_type=content_type,
            word_count=word_count,
            reading_time_minutes=reading_time_minutes,
            analysis_metadata={}
        )
    
    def _extract_sentiment(self, text: str) -> str:
        """Extract sentiment from text using keyword analysis"""
        positive_words = ["excellent", "great", "amazing", "wonderful", "fantastic", "good", "useful", "helpful", "valuable"]
        negative_words = ["bad", "terrible", "awful", "horrible", "useless", "poor", "disappointing", "frustrating"]
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return "Positive"
        elif negative_count > positive_count:
            return "Negative"
        else:
            return "Neutral"
    
    def _extract_complexity(self, text: str) -> str:
        """Extract complexity level from text"""
        complex_indicators = ["algorithm", "implementation", "architecture", "framework", "technical", "advanced", "complex"]
        simple_indicators = ["basic", "simple", "easy", "beginner", "introduction", "overview"]
        
        text_lower = text.lower()
        complex_count = sum(1 for word in complex_indicators if word in text_lower)
        simple_count = sum(1 for word in simple_indicators if word in text_lower)
        
        if complex_count > simple_count:
            return "High"
        elif simple_count > complex_count:
            return "Low"
        else:
            return "Medium"
    
    def _extract_content_type(self, content: str) -> str:
        """Extract content type from content"""
        content_lower = content.lower()
        
        if "tutorial" in content_lower or "how to" in content_lower:
            return "Tutorial"
        elif "review" in content_lower or "comparison" in content_lower:
            return "Review"
        elif "news" in content_lower or "announcement" in content_lower:
            return "News"
        elif "research" in content_lower or "study" in content_lower:
            return "Research"
        elif "opinion" in content_lower or "thoughts" in content_lower:
            return "Opinion"
        else:
            return "Article"
    
    def _extract_topics_fallback(self, content: str) -> List[str]:
        """Fallback topic extraction using keyword analysis"""
        # Simple keyword-based topic extraction
        tech_keywords = ["python", "javascript", "react", "machine learning", "ai", "blockchain", "docker", "kubernetes"]
        business_keywords = ["startup", "business", "marketing", "sales", "strategy", "growth"]
        
        topics = []
        content_lower = content.lower()
        
        for keyword in tech_keywords:
            if keyword in content_lower:
                topics.append(keyword.title())
        
        for keyword in business_keywords:
            if keyword in content_lower:
                topics.append(keyword.title())
        
        return topics[:5]
    
    def _extract_insights_fallback(self, content: str) -> List[str]:
        """Fallback insight extraction"""
        # Extract sentences that might contain insights
        sentences = content.split('.')
        insights = []
        
        insight_indicators = ["important", "key", "crucial", "essential", "main", "primary", "significant"]
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20 and any(indicator in sentence.lower() for indicator in insight_indicators):
                insights.append(sentence)
        
        return insights[:3]
    
    async def analyze_batch(self, 
                          contents: List[str],
                          preferred_provider: str = None) -> List[ContentAnalysisResult]:
        """Analyze multiple contents in batch"""
        
        # Process with concurrency control
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent analyses
        
        async def analyze_with_semaphore(content):
            async with semaphore:
                return await self.analyze(content, preferred_provider)
        
        tasks = [analyze_with_semaphore(content) for content in contents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error in batch analysis: {str(result)}")
                # Add a default result for failed analyses
                valid_results.append(ContentAnalysisResult(
                    main_topics=[],
                    key_insights=[],
                    actionable_items=[],
                    technologies_tools=[],
                    author_expertise="Unknown",
                    relevance_score=1.0,
                    sentiment="Neutral",
                    complexity_level="Medium",
                    content_type="Article",
                    word_count=0,
                    reading_time_minutes=0.0,
                    analysis_metadata={"error": str(result)}
                ))
            else:
                valid_results.append(result)
        
        return valid_results
    
    def get_analysis_summary(self, results: List[ContentAnalysisResult]) -> Dict[str, Any]:
        """Get summary statistics from analysis results"""
        
        if not results:
            return {}
        
        total_results = len(results)
        
        # Aggregate topics
        all_topics = []
        for result in results:
            all_topics.extend(result.main_topics)
        
        topic_counts = {}
        for topic in all_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        # Calculate averages
        avg_relevance = sum(r.relevance_score for r in results) / total_results
        avg_word_count = sum(r.word_count for r in results) / total_results
        avg_reading_time = sum(r.reading_time_minutes for r in results) / total_results
        
        # Content type distribution
        content_types = {}
        for result in results:
            content_types[result.content_type] = content_types.get(result.content_type, 0) + 1
        
        # Complexity distribution
        complexity_levels = {}
        for result in results:
            complexity_levels[result.complexity_level] = complexity_levels.get(result.complexity_level, 0) + 1
        
        return {
            "total_analyzed": total_results,
            "top_topics": dict(sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            "average_relevance_score": round(avg_relevance, 2),
            "average_word_count": round(avg_word_count, 0),
            "average_reading_time": round(avg_reading_time, 1),
            "content_type_distribution": content_types,
            "complexity_distribution": complexity_levels,
            "analysis_timestamp": datetime.now().isoformat()
        }