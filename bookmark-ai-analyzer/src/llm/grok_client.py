"""Grok (X.AI) LLM client implementation."""

from typing import Any, Dict, List, Optional
import asyncio
import json

from openai import AsyncOpenAI  # Grok uses OpenAI-compatible API

from .base_client import BaseLLMClient, LLMResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


class GrokClient(BaseLLMClient):
    """Grok API client implementation."""
    
    # Pricing per 1M tokens (estimated)
    PRICING = {
        "grok-beta": {
            "input": 5.0,    # $5 per 1M input tokens (estimated)
            "output": 15.0,  # $15 per 1M output tokens (estimated)
        },
    }
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Grok client."""
        super().__init__(config)
        
        # Grok uses OpenAI-compatible API
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=config.get("base_url", "https://api.x.ai/v1"),
            timeout=self.timeout,
        )
        
    async def _make_request(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Make request to Grok API."""
        try:
            # Make API call using OpenAI-compatible interface
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature),
            )
            
            # Convert to dict for consistent handling
            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "finish_reason": response.choices[0].finish_reason,
                "id": response.id,
            }
            
        except Exception as e:
            logger.error(f"Grok API request failed: {str(e)}")
            raise
    
    def _parse_response(self, response: Dict[str, Any]) -> LLMResponse:
        """Parse Grok API response."""
        usage = response["usage"]
        cost = self._calculate_cost(usage)
        
        return LLMResponse(
            content=response["content"],
            model=response["model"],
            usage=usage,
            metadata={
                "finish_reason": response.get("finish_reason"),
                "message_id": response.get("id"),
            },
            latency=0.0,  # Set by parent
            cost=cost,
        )
    
    def _calculate_cost(self, usage: Dict[str, int]) -> float:
        """Calculate cost based on token usage."""
        pricing = self.PRICING.get(self.model, self.PRICING["grok-beta"])
        
        input_cost = (usage["input_tokens"] / 1_000_000) * pricing["input"]
        output_cost = (usage["output_tokens"] / 1_000_000) * pricing["output"]
        
        return input_cost + output_cost
    
    async def analyze_tweet(
        self,
        tweet_content: str,
        author: Optional[str] = None,
        engagement_metrics: Optional[Dict[str, int]] = None
    ) -> LLMResponse:
        """
        Specialized analysis for tweets.
        
        Args:
            tweet_content: Tweet text
            author: Tweet author
            engagement_metrics: Likes, retweets, etc.
            
        Returns:
            Tweet analysis
        """
        context = f"Author: @{author}\n" if author else ""
        if engagement_metrics:
            context += f"Engagement: {engagement_metrics}\n"
            
        prompt = f"""{context}
Tweet: {tweet_content}

Analyze this tweet and provide:
1. Main topic and sentiment
2. Key insights or claims
3. Educational value (1-10)
4. Virality factors
5. Suggested categories and tags
6. Thread potential (is this part of valuable thread?)

Format as JSON with clear structure."""
        
        system_prompt = """You are an expert social media analyst specializing 
        in X/Twitter content. You understand viral mechanics, thread structures, 
        and can identify high-value educational content."""
        
        return await self.complete(prompt, system_prompt)
    
    async def analyze_thread(
        self,
        thread_tweets: List[str],
        author: Optional[str] = None
    ) -> LLMResponse:
        """
        Analyze a Twitter thread.
        
        Args:
            thread_tweets: List of tweets in thread
            author: Thread author
            
        Returns:
            Thread analysis
        """
        # Combine thread tweets
        thread_content = "\n---\n".join(
            f"Tweet {i+1}: {tweet}" 
            for i, tweet in enumerate(thread_tweets[:20])  # Limit to 20 tweets
        )
        
        prompt = f"""Author: @{author if author else 'Unknown'}
Thread ({len(thread_tweets)} tweets):
{thread_content}

Analyze this thread comprehensively:
1. Main topic and narrative arc
2. Key insights and takeaways
3. Educational structure and value
4. Action items or recommendations
5. Thread quality score (1-10)
6. Suggested categories and tags
7. Learning objectives

Format as structured JSON."""
        
        system_prompt = """You are an expert at analyzing Twitter threads, 
        especially educational and informative content. Extract maximum value 
        from thread structures and identify key learning points."""
        
        return await self.complete(prompt, system_prompt)
    
    async def identify_trends(
        self,
        bookmarks: List[Dict[str, Any]],
        time_period: str = "recent"
    ) -> LLMResponse:
        """
        Identify trends in bookmarked content.
        
        Args:
            bookmarks: List of bookmark data
            time_period: Analysis period
            
        Returns:
            Trend analysis
        """
        # Prepare bookmark summary
        bookmark_summary = []
        for i, bookmark in enumerate(bookmarks[:50]):  # Limit to 50
            summary = f"{i+1}. {bookmark.get('title', 'Untitled')} - "
            summary += f"Category: {bookmark.get('category', 'Unknown')}"
            if tags := bookmark.get('tags'):
                summary += f", Tags: {', '.join(tags[:3])}"
            bookmark_summary.append(summary)
            
        prompt = f"""Analyze these bookmarked items from {time_period}:

{chr(10).join(bookmark_summary)}

Identify:
1. Top 5 trending topics
2. Emerging themes
3. Knowledge gaps (what's missing)
4. Learning path recommendations
5. Content quality insights
6. Actionable next steps

Format as structured JSON with clear insights."""
        
        system_prompt = """You are a content trend analyst specializing in 
        professional development and learning content. Identify patterns and 
        provide actionable insights for knowledge management."""
        
        return await self.complete(prompt, system_prompt)
    
    async def generate_twitter_summary(
        self,
        content: str,
        style: str = "informative"
    ) -> LLMResponse:
        """
        Generate Twitter-friendly summary.
        
        Args:
            content: Content to summarize
            style: Summary style
            
        Returns:
            Twitter summary
        """
        styles = {
            "informative": "Clear, educational, with key points",
            "engaging": "Hook-driven, curiosity-inducing",
            "thread": "Thread-style with numbered points",
        }
        
        prompt = f"""Create a Twitter summary of this content.
Style: {styles.get(style, styles['informative'])}

Content: {content[:2000]}

Generate:
1. Main tweet (under 280 chars)
2. 3-5 key points (each under 280 chars)
3. Relevant hashtags
4. Call-to-action

Format as JSON."""
        
        system_prompt = """You are a Twitter content expert who creates 
        engaging, valuable summaries that drive engagement while maintaining 
        educational value."""
        
        return await self.complete(prompt, system_prompt)