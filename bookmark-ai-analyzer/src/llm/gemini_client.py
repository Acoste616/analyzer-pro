"""Google Gemini LLM client implementation."""

from typing import Any, Dict, List, Optional
import asyncio
import json

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from .base_client import BaseLLMClient, LLMResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


class GeminiClient(BaseLLMClient):
    """Gemini API client implementation."""
    
    # Pricing per 1M tokens (as of 2024)
    PRICING = {
        "gemini-pro": {
            "input": 0.5,    # $0.50 per 1M input tokens
            "output": 1.5,   # $1.50 per 1M output tokens
        },
        "gemini-pro-vision": {
            "input": 0.5,    # $0.50 per 1M input tokens
            "output": 1.5,   # $1.50 per 1M output tokens
        },
    }
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Gemini client."""
        super().__init__(config)
        
        # Configure API
        genai.configure(api_key=self.api_key)
        
        # Initialize model
        self.model_instance = genai.GenerativeModel(
            model_name=self.model,
            generation_config={
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        )
        
    async def _make_request(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Make request to Gemini API."""
        try:
            # Convert messages to Gemini format
            prompt_parts = []
            
            for msg in messages:
                if msg["role"] == "system":
                    prompt_parts.append(f"System: {msg['content']}\n\n")
                elif msg["role"] == "user":
                    prompt_parts.append(f"User: {msg['content']}\n\n")
                elif msg["role"] == "assistant":
                    prompt_parts.append(f"Assistant: {msg['content']}\n\n")
            
            prompt = "".join(prompt_parts) + "Assistant: "
            
            # Make async call
            response = await asyncio.to_thread(
                self.model_instance.generate_content,
                prompt,
                generation_config={
                    "temperature": kwargs.get("temperature", self.temperature),
                    "max_output_tokens": kwargs.get("max_tokens", self.max_tokens),
                }
            )
            
            # Extract token counts (approximation for Gemini)
            input_tokens = len(prompt.split()) * 1.3  # Rough approximation
            output_tokens = len(response.text.split()) * 1.3
            
            return {
                "content": response.text,
                "model": self.model,
                "usage": {
                    "input_tokens": int(input_tokens),
                    "output_tokens": int(output_tokens),
                    "total_tokens": int(input_tokens + output_tokens),
                },
                "safety_ratings": [
                    {
                        "category": rating.category.name,
                        "probability": rating.probability.name
                    }
                    for rating in response.prompt_feedback.safety_ratings
                ] if hasattr(response, 'prompt_feedback') else [],
            }
            
        except Exception as e:
            logger.error(f"Gemini API request failed: {str(e)}")
            raise
    
    def _parse_response(self, response: Dict[str, Any]) -> LLMResponse:
        """Parse Gemini API response."""
        usage = response["usage"]
        cost = self._calculate_cost(usage)
        
        return LLMResponse(
            content=response["content"],
            model=response["model"],
            usage=usage,
            metadata={
                "safety_ratings": response.get("safety_ratings", []),
            },
            latency=0.0,  # Set by parent
            cost=cost,
        )
    
    def _calculate_cost(self, usage: Dict[str, int]) -> float:
        """Calculate cost based on token usage."""
        pricing = self.PRICING.get(self.model, self.PRICING["gemini-pro"])
        
        input_cost = (usage["input_tokens"] / 1_000_000) * pricing["input"]
        output_cost = (usage["output_tokens"] / 1_000_000) * pricing["output"]
        
        return input_cost + output_cost
    
    async def analyze_multimodal_content(
        self,
        text: str,
        image_urls: Optional[List[str]] = None
    ) -> LLMResponse:
        """
        Analyze content with both text and images.
        
        Args:
            text: Text content
            image_urls: List of image URLs
            
        Returns:
            Analysis response
        """
        prompt = f"""Analyze this content comprehensively:

Text: {text[:3000]}

Provide:
1. Main topics and themes
2. Visual elements description (if images present)
3. Key insights
4. Educational value
5. Suggested tags and categories

Format as structured JSON."""
        
        system_prompt = """You are a multimodal content analyst expert. 
        Analyze both textual and visual elements to provide comprehensive 
        insights."""
        
        # For now, just analyze text
        # TODO: Implement actual image analysis when needed
        return await self.complete(prompt, system_prompt)
    
    async def transcribe_video_content(
        self,
        video_url: str,
        duration_minutes: Optional[int] = None
    ) -> LLMResponse:
        """
        Generate structured notes from video content.
        
        Args:
            video_url: URL of the video
            duration_minutes: Video duration
            
        Returns:
            Structured notes
        """
        # This would integrate with actual transcription service
        # For now, return a template response
        prompt = f"""Create a structured learning outline for a video course.

Video URL: {video_url}
Duration: {duration_minutes or 'Unknown'} minutes

Generate a comprehensive outline including:
1. Course overview
2. Main sections with time estimates
3. Key concepts covered
4. Learning objectives
5. Prerequisites
6. Hands-on exercises

Format as structured JSON suitable for a learning management system."""
        
        system_prompt = """You are an expert in creating educational content 
        structures. Generate comprehensive, actionable learning outlines."""
        
        return await self.complete(prompt, system_prompt)
    
    async def generate_quiz_questions(
        self,
        content: str,
        num_questions: int = 5
    ) -> LLMResponse:
        """
        Generate quiz questions from content.
        
        Args:
            content: Content to generate questions from
            num_questions: Number of questions
            
        Returns:
            Quiz questions
        """
        prompt = f"""Generate {num_questions} quiz questions from this content.

Content: {content[:3000]}

For each question provide:
1. Question text
2. 4 multiple choice options
3. Correct answer
4. Explanation
5. Difficulty level (easy/medium/hard)

Format as JSON array."""
        
        system_prompt = """You are an expert educator skilled at creating 
        effective assessment questions that test understanding, not just 
        memorization."""
        
        return await self.complete(prompt, system_prompt)