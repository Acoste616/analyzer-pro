"""Content analysis module for deep content understanding."""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import asyncio

from ..llm import BaseLLMClient, ClaudeClient, GeminiClient, GrokClient
from ..utils.logger import get_logger, log_execution_time
from ..utils.validation import ContentQuality, is_spam_content
from ..config import get_settings

logger = get_logger(__name__)


class ContentAnalyzer:
    """Analyze content using LLM providers for deep understanding."""
    
    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        """
        Initialize content analyzer.
        
        Args:
            llm_client: LLM client to use for analysis
        """
        self.settings = get_settings()
        self.llm_client = llm_client or self._get_default_llm_client()
        self.analysis_cache: Dict[str, Dict[str, Any]] = {}
        
    def _get_default_llm_client(self) -> BaseLLMClient:
        """Get default LLM client based on configuration."""
        settings = self.settings
        
        if settings.default_llm == "claude" and settings.claude:
            return ClaudeClient(settings.claude.dict())
        elif settings.default_llm == "gemini" and settings.gemini:
            return GeminiClient(settings.gemini.dict())
        elif settings.default_llm == "grok" and settings.grok:
            return GrokClient(settings.grok.dict())
        else:
            raise ValueError(f"No configuration found for {settings.default_llm}")
    
    @log_execution_time
    async def analyze_content(
        self,
        content_item: Dict[str, Any],
        analysis_depth: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        Perform deep content analysis.
        
        Args:
            content_item: Content to analyze (tweet, thread, video, etc.)
            analysis_depth: Level of analysis (quick, standard, comprehensive)
            
        Returns:
            Analysis results
        """
        content_id = content_item.get('id', '')
        
        # Check cache
        cache_key = f"{content_id}_{analysis_depth}"
        if cache_key in self.analysis_cache:
            logger.debug(f"Returning cached analysis for {content_id}")
            return self.analysis_cache[cache_key]
        
        # Perform analysis based on content type
        content_type = content_item.get('type', 'unknown')
        
        if content_type == 'tweet':
            analysis = await self._analyze_tweet(content_item, analysis_depth)
        elif content_type == 'thread':
            analysis = await self._analyze_thread(content_item, analysis_depth)
        elif content_type == 'video':
            analysis = await self._analyze_video(content_item, analysis_depth)
        else:
            analysis = await self._analyze_generic(content_item, analysis_depth)
        
        # Add common analysis elements
        analysis.update({
            'content_id': content_id,
            'content_type': content_type,
            'analysis_timestamp': datetime.now().isoformat(),
            'analysis_depth': analysis_depth,
            'quality_metrics': self._calculate_quality_metrics(content_item),
        })
        
        # Cache the result
        self.analysis_cache[cache_key] = analysis
        
        return analysis
    
    async def _analyze_tweet(
        self,
        tweet: Dict[str, Any],
        analysis_depth: str
    ) -> Dict[str, Any]:
        """Analyze tweet content."""
        content = tweet.get('content', '')
        metadata = tweet.get('metadata', {})
        
        # Use Grok for tweet analysis (optimized for Twitter)
        if isinstance(self.llm_client, GrokClient):
            response = await self.llm_client.analyze_tweet(
                content,
                author=tweet.get('author'),
                engagement_metrics=metadata.get('engagement_metrics')
            )
        else:
            # Fallback to generic analysis
            prompt = self._create_tweet_analysis_prompt(tweet, analysis_depth)
            response = await self.llm_client.complete(prompt)
        
        try:
            analysis = json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback to text analysis
            analysis = {
                'raw_analysis': response.content,
                'parse_error': True
            }
        
        return analysis
    
    async def _analyze_thread(
        self,
        thread: Dict[str, Any],
        analysis_depth: str
    ) -> Dict[str, Any]:
        """Analyze thread content."""
        content = thread.get('content', '')
        tweets = thread.get('tweets', [])
        
        # Use Claude for deep thread analysis
        if isinstance(self.llm_client, ClaudeClient):
            response = await self.llm_client.analyze_content(
                content,
                analysis_type="comprehensive"
            )
        else:
            prompt = self._create_thread_analysis_prompt(thread, analysis_depth)
            response = await self.llm_client.complete(prompt)
        
        try:
            analysis = json.loads(response.content)
        except json.JSONDecodeError:
            analysis = {'raw_analysis': response.content, 'parse_error': True}
        
        # Add thread-specific analysis
        analysis['thread_metrics'] = {
            'tweet_count': len(tweets),
            'total_length': len(content),
            'avg_tweet_length': len(content) / len(tweets) if tweets else 0,
        }
        
        return analysis
    
    async def _analyze_video(
        self,
        video: Dict[str, Any],
        analysis_depth: str
    ) -> Dict[str, Any]:
        """Analyze video content."""
        title = video.get('title', '')
        description = video.get('description', '')
        transcript = video.get('content', '')
        
        # Combine available text
        combined_text = f"Title: {title}\n\nDescription: {description}\n\nTranscript: {transcript[:2000]}"
        
        # Use Gemini for multimodal content if available
        if isinstance(self.llm_client, GeminiClient):
            response = await self.llm_client.analyze_multimodal_content(
                combined_text,
                image_urls=[video.get('metadata', {}).get('thumbnail')]
            )
        else:
            prompt = self._create_video_analysis_prompt(video, analysis_depth)
            response = await self.llm_client.complete(prompt)
        
        try:
            analysis = json.loads(response.content)
        except json.JSONDecodeError:
            analysis = {'raw_analysis': response.content, 'parse_error': True}
        
        # Add video-specific metrics
        analysis['video_metrics'] = {
            'duration': video.get('duration', 0),
            'has_chapters': video.get('metadata', {}).get('has_chapters', False),
            'has_transcript': bool(transcript),
            'platform': video.get('platform', 'unknown'),
        }
        
        return analysis
    
    async def _analyze_generic(
        self,
        content_item: Dict[str, Any],
        analysis_depth: str
    ) -> Dict[str, Any]:
        """Generic content analysis."""
        content = content_item.get('content', '')
        
        prompt = f"""Analyze this content and provide:
1. Main topic and themes
2. Key insights and takeaways
3. Quality assessment (1-10)
4. Target audience
5. Practical applications

Content: {content[:3000]}

Provide response in JSON format."""
        
        response = await self.llm_client.complete(prompt)
        
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {'raw_analysis': response.content, 'parse_error': True}
    
    def _create_tweet_analysis_prompt(
        self,
        tweet: Dict[str, Any],
        analysis_depth: str
    ) -> str:
        """Create analysis prompt for tweets."""
        content = tweet.get('content', '')
        author = tweet.get('author', 'Unknown')
        
        if analysis_depth == "quick":
            return f"""Quick analysis of this tweet:
Author: @{author}
Tweet: {content}

Provide: topic, sentiment, key_point, value_score (1-10)
Format: JSON"""
        
        elif analysis_depth == "comprehensive":
            return f"""Comprehensive analysis of this tweet:
Author: @{author}
Tweet: {content}
Metadata: {json.dumps(tweet.get('metadata', {}), indent=2)}

Analyze:
1. Main topic and subtopics
2. Sentiment and tone
3. Key insights or claims
4. Educational value (1-10)
5. Virality factors
6. Target audience
7. Actionable takeaways
8. Related topics to explore

Format response as structured JSON."""
        
        else:  # standard
            return f"""Analyze this tweet:
Author: @{author}
Tweet: {content}

Provide:
1. Main topic
2. Key insights
3. Quality score (1-10)
4. Suggested tags
5. Summary

Format: JSON"""
    
    def _create_thread_analysis_prompt(
        self,
        thread: Dict[str, Any],
        analysis_depth: str
    ) -> str:
        """Create analysis prompt for threads."""
        content = thread.get('content', '')
        tweet_count = thread.get('tweet_count', 0)
        
        return f"""Analyze this Twitter thread ({tweet_count} tweets):

{content[:4000]}

Provide comprehensive analysis:
1. Main narrative and structure
2. Key arguments and evidence
3. Learning objectives
4. Quality and depth assessment (1-10)
5. Target audience and prerequisites
6. Actionable insights
7. Related resources mentioned
8. Suggested follow-up topics

Format as structured JSON with clear sections."""
    
    def _create_video_analysis_prompt(
        self,
        video: Dict[str, Any],
        analysis_depth: str
    ) -> str:
        """Create analysis prompt for videos."""
        title = video.get('title', '')
        description = video.get('description', '')
        duration = video.get('duration', 0)
        
        return f"""Analyze this educational video:
Title: {title}
Duration: {duration // 60} minutes
Description: {description[:500]}

Provide:
1. Learning objectives
2. Key topics covered
3. Target skill level
4. Prerequisites
5. Practical applications
6. Quality assessment (1-10)
7. Recommended follow-up resources

Format as structured JSON."""
    
    def _calculate_quality_metrics(self, content_item: Dict[str, Any]) -> Dict[str, float]:
        """Calculate quality metrics for content."""
        content = content_item.get('content', '')
        
        # Basic quality assessment
        quality = ContentQuality(content)
        
        metrics = {
            'content_quality_score': quality.quality_score,
            'word_count': quality.word_count,
            'has_links': quality.has_links,
            'language': quality.language,
            'is_spam': is_spam_content(content),
        }
        
        # Type-specific metrics
        content_type = content_item.get('type', '')
        
        if content_type == 'thread':
            metrics['thread_coherence'] = self._calculate_thread_coherence(content_item)
        elif content_type == 'video':
            metrics['video_educational_score'] = self._calculate_video_educational_score(content_item)
        
        return metrics
    
    def _calculate_thread_coherence(self, thread: Dict[str, Any]) -> float:
        """Calculate coherence score for threads."""
        tweets = thread.get('tweets', [])
        if len(tweets) < 2:
            return 1.0
        
        # Simple coherence based on consistent topics/keywords
        all_words = []
        for tweet in tweets:
            words = tweet.get('content', '').lower().split()
            all_words.extend(words)
        
        # Check for repeated key terms (indicates coherent theme)
        word_freq = {}
        for word in all_words:
            if len(word) > 4:  # Skip short words
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Calculate coherence based on term repetition
        repeated_terms = sum(1 for count in word_freq.values() if count > 1)
        coherence = min(1.0, repeated_terms / (len(tweets) * 2))
        
        return coherence
    
    def _calculate_video_educational_score(self, video: Dict[str, Any]) -> float:
        """Calculate educational value score for videos."""
        score = 0.0
        
        # Check for educational indicators
        if video.get('metadata', {}).get('is_educational'):
            score += 0.3
        
        # Chapters indicate structured content
        if video.get('chapters'):
            score += 0.2
        
        # Transcript availability
        if video.get('content'):
            score += 0.2
        
        # Duration (educational content tends to be longer)
        duration = video.get('duration', 0)
        if 600 < duration < 3600:  # 10-60 minutes
            score += 0.2
        elif duration >= 3600:  # Over 1 hour
            score += 0.1
        
        # Platform bonus
        educational_platforms = ['coursera', 'udemy', 'pluralsight', 'linkedin_learning']
        if video.get('platform') in educational_platforms:
            score += 0.1
        
        return min(1.0, score)
    
    async def batch_analyze(
        self,
        content_items: List[Dict[str, Any]],
        analysis_depth: str = "standard",
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple content items concurrently.
        
        Args:
            content_items: List of content to analyze
            analysis_depth: Level of analysis
            max_concurrent: Maximum concurrent analyses
            
        Returns:
            List of analysis results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def analyze_with_semaphore(item):
            async with semaphore:
                return await self.analyze_content(item, analysis_depth)
        
        tasks = [analyze_with_semaphore(item) for item in content_items]
        return await asyncio.gather(*tasks)
    
    def get_analysis_summary(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary of multiple analyses.
        
        Args:
            analyses: List of analysis results
            
        Returns:
            Summary statistics and insights
        """
        if not analyses:
            return {}
        
        summary = {
            'total_analyzed': len(analyses),
            'average_quality': sum(
                a.get('quality_metrics', {}).get('content_quality_score', 0)
                for a in analyses
            ) / len(analyses),
            'content_types': {},
            'top_topics': {},
            'quality_distribution': {
                'high': 0,  # > 0.7
                'medium': 0,  # 0.4-0.7
                'low': 0,  # < 0.4
            },
        }
        
        # Count content types
        for analysis in analyses:
            content_type = analysis.get('content_type', 'unknown')
            summary['content_types'][content_type] = summary['content_types'].get(content_type, 0) + 1
            
            # Quality distribution
            quality = analysis.get('quality_metrics', {}).get('content_quality_score', 0)
            if quality > 0.7:
                summary['quality_distribution']['high'] += 1
            elif quality > 0.4:
                summary['quality_distribution']['medium'] += 1
            else:
                summary['quality_distribution']['low'] += 1
        
        return summary