import os
from typing import Dict, Any, Optional
from datetime import datetime

from .base_client import BaseLLMClient, LLMResponse


class GrokClient(BaseLLMClient):
    def __init__(self):
        super().__init__("grok")
        self.api_key = os.getenv("GROK_API_KEY")
        if not self.api_key:
            raise ValueError("GROK_API_KEY environment variable is required")
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _get_endpoint_url(self) -> str:
        return f"{self.config['base_url']}/chat/completions"
    
    def _prepare_request(self, prompt: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        request_data = {
            "model": self.config.get("model", "grok-beta"),
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "top_p": kwargs.get("top_p", 0.9),
            "frequency_penalty": kwargs.get("frequency_penalty", 0),
            "presence_penalty": kwargs.get("presence_penalty", 0)
        }
        
        # Add stream parameter if specified
        if kwargs.get("stream", False):
            request_data["stream"] = True
        
        return request_data
    
    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        if "choices" not in response_data or not response_data["choices"]:
            raise ValueError("Invalid response format from Grok API")
        
        choice = response_data["choices"][0]
        content = choice.get("message", {}).get("content", "")
        
        # Extract usage information
        usage = response_data.get("usage", {})
        
        # Extract model information
        model = response_data.get("model", self.config.get("model", "grok-beta"))
        
        # Extract metadata
        metadata = {
            "finish_reason": choice.get("finish_reason"),
            "id": response_data.get("id"),
            "object": response_data.get("object"),
            "created": response_data.get("created")
        }
        
        return LLMResponse(
            content=content,
            usage=usage,
            model=model,
            created_at=datetime.now(),
            processing_time=0.0,  # Will be set by the base client
            metadata=metadata
        )
    
    async def generate_with_tools(self, 
                                prompt: str, 
                                tools: list,
                                system_prompt: str = None,
                                **kwargs) -> LLMResponse:
        """Generate response with function calling capabilities"""
        
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        request_data = {
            "model": self.config.get("model", "grok-beta"),
            "messages": messages,
            "tools": tools,
            "tool_choice": kwargs.get("tool_choice", "auto"),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7))
        }
        
        # Wait for rate limit slot
        estimated_tokens = self.estimate_tokens(prompt)
        await self.rate_limiter.wait_for_slot(estimated_tokens)
        
        try:
            response_data = await self._make_request_with_retry(request_data)
            return self._parse_response(response_data)
        except Exception as e:
            self.logger.error(f"Error in Grok function calling: {str(e)}")
            raise
    
    async def generate_structured(self, 
                                prompt: str,
                                response_format: Dict[str, Any],
                                system_prompt: str = None,
                                **kwargs) -> LLMResponse:
        """Generate structured response (JSON mode)"""
        
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system", 
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        request_data = {
            "model": self.config.get("model", "grok-beta"),
            "messages": messages,
            "response_format": response_format,
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7))
        }
        
        # Wait for rate limit slot
        estimated_tokens = self.estimate_tokens(prompt)
        await self.rate_limiter.wait_for_slot(estimated_tokens)
        
        try:
            response_data = await self._make_request_with_retry(request_data)
            return self._parse_response(response_data)
        except Exception as e:
            self.logger.error(f"Error in Grok structured generation: {str(e)}")
            raise
    
    def get_available_models(self) -> list:
        """Get list of available Grok models"""
        return [
            "grok-beta",
            "grok-vision-beta"
        ]
    
    def validate_config(self) -> bool:
        """Validate Grok-specific configuration"""
        if not super().validate_config():
            return False
        
        if not self.api_key:
            self.logger.error("GROK_API_KEY environment variable is not set")
            return False
        
        return True