import os
from typing import Dict, Any, Optional
from datetime import datetime

from .base_client import BaseLLMClient, LLMResponse


class ClaudeClient(BaseLLMClient):
    def __init__(self):
        super().__init__("claude")
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
    
    def _get_endpoint_url(self) -> str:
        return f"{self.config['base_url']}/messages"
    
    def _prepare_request(self, prompt: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        messages = [{
            "role": "user",
            "content": prompt
        }]
        
        request_data = {
            "model": self.config.get("model", "claude-3-sonnet-20240229"),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "messages": messages
        }
        
        # Add system prompt if provided
        if system_prompt:
            request_data["system"] = system_prompt
        
        # Add optional parameters
        if kwargs.get("top_p"):
            request_data["top_p"] = kwargs["top_p"]
        
        if kwargs.get("top_k"):
            request_data["top_k"] = kwargs["top_k"]
        
        if kwargs.get("stop_sequences"):
            request_data["stop_sequences"] = kwargs["stop_sequences"]
        
        return request_data
    
    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        if "content" not in response_data or not response_data["content"]:
            raise ValueError("Invalid response format from Claude API")
        
        # Extract content (Claude returns list of content blocks)
        content_blocks = response_data["content"]
        content = ""
        
        for block in content_blocks:
            if block.get("type") == "text":
                content += block.get("text", "")
        
        # Extract usage information
        usage = response_data.get("usage", {})
        
        # Extract model information
        model = response_data.get("model", self.config.get("model"))
        
        # Extract metadata
        metadata = {
            "id": response_data.get("id"),
            "type": response_data.get("type"),
            "role": response_data.get("role"),
            "stop_reason": response_data.get("stop_reason"),
            "stop_sequence": response_data.get("stop_sequence")
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
        """Generate response with tool use capabilities"""
        
        messages = [{
            "role": "user",
            "content": prompt
        }]
        
        request_data = {
            "model": self.config.get("model", "claude-3-sonnet-20240229"),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "messages": messages,
            "tools": tools
        }
        
        # Add system prompt if provided
        if system_prompt:
            request_data["system"] = system_prompt
        
        # Add tool choice if specified
        if kwargs.get("tool_choice"):
            request_data["tool_choice"] = kwargs["tool_choice"]
        
        # Wait for rate limit slot
        estimated_tokens = self.estimate_tokens(prompt)
        await self.rate_limiter.wait_for_slot(estimated_tokens)
        
        try:
            response_data = await self._make_request_with_retry(request_data)
            return self._parse_response(response_data)
        except Exception as e:
            self.logger.error(f"Error in Claude tool use: {str(e)}")
            raise
    
    async def generate_with_images(self, 
                                 prompt: str,
                                 images: list,
                                 system_prompt: str = None,
                                 **kwargs) -> LLMResponse:
        """Generate response with image inputs"""
        
        # Prepare content with images
        content = []
        
        # Add images first
        for image in images:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image.get("media_type", "image/jpeg"),
                    "data": image.get("data")
                }
            })
        
        # Add text prompt
        content.append({
            "type": "text",
            "text": prompt
        })
        
        messages = [{
            "role": "user",
            "content": content
        }]
        
        request_data = {
            "model": self.config.get("model", "claude-3-sonnet-20240229"),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "messages": messages
        }
        
        # Add system prompt if provided
        if system_prompt:
            request_data["system"] = system_prompt
        
        # Wait for rate limit slot
        estimated_tokens = self.estimate_tokens(prompt)
        await self.rate_limiter.wait_for_slot(estimated_tokens)
        
        try:
            response_data = await self._make_request_with_retry(request_data)
            return self._parse_response(response_data)
        except Exception as e:
            self.logger.error(f"Error in Claude image generation: {str(e)}")
            raise
    
    async def generate_streaming(self, 
                               prompt: str,
                               system_prompt: str = None,
                               **kwargs):
        """Generate streaming response"""
        
        messages = [{
            "role": "user",
            "content": prompt
        }]
        
        request_data = {
            "model": self.config.get("model", "claude-3-sonnet-20240229"),
            "max_tokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "messages": messages,
            "stream": True
        }
        
        # Add system prompt if provided
        if system_prompt:
            request_data["system"] = system_prompt
        
        # Wait for rate limit slot
        estimated_tokens = self.estimate_tokens(prompt)
        await self.rate_limiter.wait_for_slot(estimated_tokens)
        
        try:
            async with self.session.post(
                self._get_endpoint_url(),
                json=request_data
            ) as response:
                response.raise_for_status()
                
                async for line in response.content:
                    if line:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            data = line[6:]  # Remove 'data: ' prefix
                            if data == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data)
                                yield chunk
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            self.logger.error(f"Error in Claude streaming: {str(e)}")
            raise
    
    def get_available_models(self) -> list:
        """Get list of available Claude models"""
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307"
        ]
    
    def validate_config(self) -> bool:
        """Validate Claude-specific configuration"""
        if not super().validate_config():
            return False
        
        if not self.api_key:
            self.logger.error("ANTHROPIC_API_KEY environment variable is not set")
            return False
        
        return True