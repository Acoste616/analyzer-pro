"""Claude (Anthropic) LLM client implementation."""

from typing import Any, Dict, List
import asyncio

from anthropic import AsyncAnthropic
from anthropic.types import Message

from .base_client import BaseLLMClient, LLMResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeClient(BaseLLMClient):
    """Claude API client implementation."""
    
    # Pricing per 1M tokens (as of 2024)
    PRICING = {
        "claude-3-opus-20240229": {
            "input": 15.0,   # $15 per 1M input tokens
            "output": 75.0,  # $75 per 1M output tokens
        },
        "claude-3-sonnet-20240229": {
            "input": 3.0,    # $3 per 1M input tokens
            "output": 15.0,  # $15 per 1M output tokens
        },
        "claude-3-haiku-20240307": {
            "input": 0.25,   # $0.25 per 1M input tokens
            "output": 1.25,  # $1.25 per 1M output tokens
        },
    }
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Claude client."""
        super().__init__(config)
        
        self.client = AsyncAnthropic(
            api_key=self.api_key,
            timeout=self.timeout,
        )
        
        self.anthropic_version = config.get("anthropic_version", "2023-06-01")
        
    async def _make_request(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Make request to Claude API."""
        try:
            # Extract system message if present
            system_message = None
            filtered_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    filtered_messages.append(msg)
            
            # Make API call
            response = await self.client.messages.create(
                model=self.model,
                messages=filtered_messages,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature),
                system=system_message,
            )
            
            # Convert to dict for consistent handling
            return {
                "content": response.content[0].text,
                "model": response.model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": (
                        response.usage.input_tokens + 
                        response.usage.output_tokens
                    ),
                },
                "stop_reason": response.stop_reason,
                "id": response.id,
            }
            
        except Exception as e:
            logger.error(f"Claude API request failed: {str(e)}")
            raise
    
    def _parse_response(self, response: Dict[str, Any]) -> LLMResponse:
        """Parse Claude API response."""
        usage = response["usage"]
        cost = self._calculate_cost(usage)
        
        return LLMResponse(
            content=response["content"],
            model=response["model"],
            usage=usage,
            metadata={
                "stop_reason": response.get("stop_reason"),
                "message_id": response.get("id"),
            },
            latency=0.0,  # Set by parent
            cost=cost,
        )
    
    def _calculate_cost(self, usage: Dict[str, int]) -> float:
        """Calculate cost based on token usage."""
        pricing = self.PRICING.get(self.model, self.PRICING["claude-3-opus-20240229"])
        
        input_cost = (usage["input_tokens"] / 1_000_000) * pricing["input"]
        output_cost = (usage["output_tokens"] / 1_000_000) * pricing["output"]
        
        return input_cost + output_cost
    
    async def analyze_content(
        self,
        content: str,
        analysis_type: str = "comprehensive"
    ) -> LLMResponse:
        """
        Specialized method for content analysis.
        
        Args:
            content: Content to analyze
            analysis_type: Type of analysis to perform
            
        Returns:
            Analysis response
        """
        prompts = {
            "comprehensive": """Analyze the following content and provide:
1. Main topic and key themes
2. Important insights and takeaways
3. Quality assessment (1-10)
4. Suggested categories and tags
5. Learning objectives if educational
6. Time investment estimate

Content: {content}""",
            
            "categorization": """Categorize this content into one primary category and up to 3 subcategories.
Categories: Programming, Business, Technology, Education, Lifestyle, Science, Other

Content: {content}

Respond in JSON format:
{{
    "primary_category": "...",
    "subcategories": ["...", "..."],
    "confidence": 0.95
}}""",
            
            "key_points": """Extract the top 5 key points from this content.
Each point should be actionable and concise.

Content: {content}

Respond in JSON format:
{{
    "key_points": ["...", "...", "...", "...", "..."]
}}""",
        }
        
        prompt = prompts.get(analysis_type, prompts["comprehensive"]).format(
            content=content[:4000]  # Limit content length
        )
        
        system_prompt = """You are an expert content analyst specializing in 
        educational and professional development content. Provide clear, 
        structured analysis that helps users quickly understand and categorize 
        content."""
        
        return await self.complete(prompt, system_prompt)
    
    async def generate_learning_structure(
        self,
        content: str,
        content_type: str = "article"
    ) -> LLMResponse:
        """
        Generate learning structure from content.
        
        Args:
            content: Content to structure
            content_type: Type of content
            
        Returns:
            Learning structure
        """
        prompt = f"""Create a structured learning outline from this {content_type}.

Include:
1. Learning objectives (what the learner will achieve)
2. Prerequisites (required knowledge)
3. Main sections with time estimates
4. Key concepts to master
5. Practical exercises or applications
6. Additional resources needed

Content: {content[:4000]}

Respond in JSON format with clear structure."""
        
        system_prompt = """You are an instructional design expert. Create 
        clear, actionable learning structures that maximize knowledge retention 
        and practical application."""
        
        return await self.complete(prompt, system_prompt)