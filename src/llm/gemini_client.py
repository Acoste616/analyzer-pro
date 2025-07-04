import os
from typing import Dict, Any, Optional
from datetime import datetime

from .base_client import BaseLLMClient, LLMResponse


class GeminiClient(BaseLLMClient):
    def __init__(self):
        super().__init__("gemini")
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json"
        }
    
    def _get_endpoint_url(self) -> str:
        model = self.config.get("model", "gemini-1.5-pro")
        return f"{self.config['base_url']}/models/{model}:generateContent?key={self.api_key}"
    
    def _prepare_request(self, prompt: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        # Prepare contents
        contents = []
        
        # Add system instruction if provided
        system_instruction = None
        if system_prompt:
            system_instruction = {
                "parts": [{"text": system_prompt}]
            }
        
        # Add user prompt
        contents.append({
            "parts": [{"text": prompt}]
        })
        
        # Prepare generation config
        generation_config = {
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "topP": kwargs.get("top_p", 0.8),
            "topK": kwargs.get("top_k", 40),
            "maxOutputTokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096)),
            "stopSequences": kwargs.get("stop_sequences", [])
        }
        
        request_data = {
            "contents": contents,
            "generationConfig": generation_config
        }
        
        if system_instruction:
            request_data["systemInstruction"] = system_instruction
        
        # Add safety settings
        safety_settings = kwargs.get("safety_settings", [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ])
        
        request_data["safetySettings"] = safety_settings
        
        return request_data
    
    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        if "candidates" not in response_data or not response_data["candidates"]:
            raise ValueError("Invalid response format from Gemini API")
        
        candidate = response_data["candidates"][0]
        
        # Extract content
        content = ""
        if "content" in candidate and "parts" in candidate["content"]:
            for part in candidate["content"]["parts"]:
                if "text" in part:
                    content += part["text"]
        
        # Extract usage information
        usage = response_data.get("usageMetadata", {})
        
        # Extract model information
        model = self.config.get("model", "gemini-1.5-pro")
        
        # Extract metadata
        metadata = {
            "finish_reason": candidate.get("finishReason"),
            "safety_ratings": candidate.get("safetyRatings", []),
            "citation_metadata": candidate.get("citationMetadata"),
            "token_count": candidate.get("tokenCount")
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
        
        contents = []
        
        # Add user prompt
        contents.append({
            "parts": [{"text": prompt}]
        })
        
        # Prepare system instruction
        system_instruction = None
        if system_prompt:
            system_instruction = {
                "parts": [{"text": system_prompt}]
            }
        
        # Prepare generation config
        generation_config = {
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "topP": kwargs.get("top_p", 0.8),
            "topK": kwargs.get("top_k", 40),
            "maxOutputTokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096))
        }
        
        request_data = {
            "contents": contents,
            "tools": tools,
            "generationConfig": generation_config
        }
        
        if system_instruction:
            request_data["systemInstruction"] = system_instruction
        
        # Wait for rate limit slot
        estimated_tokens = self.estimate_tokens(prompt)
        await self.rate_limiter.wait_for_slot(estimated_tokens)
        
        try:
            response_data = await self._make_request_with_retry(request_data)
            return self._parse_response(response_data)
        except Exception as e:
            self.logger.error(f"Error in Gemini function calling: {str(e)}")
            raise
    
    async def generate_with_images(self, 
                                 prompt: str,
                                 images: list,
                                 system_prompt: str = None,
                                 **kwargs) -> LLMResponse:
        """Generate response with image inputs"""
        
        # Prepare content parts
        parts = []
        
        # Add images
        for image in images:
            parts.append({
                "inline_data": {
                    "mime_type": image.get("mime_type", "image/jpeg"),
                    "data": image.get("data")
                }
            })
        
        # Add text prompt
        parts.append({"text": prompt})
        
        contents = [{
            "parts": parts
        }]
        
        # Prepare system instruction
        system_instruction = None
        if system_prompt:
            system_instruction = {
                "parts": [{"text": system_prompt}]
            }
        
        # Prepare generation config
        generation_config = {
            "temperature": kwargs.get("temperature", self.config.get("temperature", 0.7)),
            "topP": kwargs.get("top_p", 0.8),
            "topK": kwargs.get("top_k", 40),
            "maxOutputTokens": kwargs.get("max_tokens", self.config.get("max_tokens", 4096))
        }
        
        request_data = {
            "contents": contents,
            "generationConfig": generation_config
        }
        
        if system_instruction:
            request_data["systemInstruction"] = system_instruction
        
        # Wait for rate limit slot
        estimated_tokens = self.estimate_tokens(prompt)
        await self.rate_limiter.wait_for_slot(estimated_tokens)
        
        try:
            response_data = await self._make_request_with_retry(request_data)
            return self._parse_response(response_data)
        except Exception as e:
            self.logger.error(f"Error in Gemini image generation: {str(e)}")
            raise
    
    async def generate_streaming(self, 
                               prompt: str,
                               system_prompt: str = None,
                               **kwargs):
        """Generate streaming response"""
        
        # Prepare request data
        request_data = self._prepare_request(prompt, system_prompt, **kwargs)
        
        # Use streaming endpoint
        model = self.config.get("model", "gemini-1.5-pro")
        url = f"{self.config['base_url']}/models/{model}:streamGenerateContent?key={self.api_key}"
        
        # Wait for rate limit slot
        estimated_tokens = self.estimate_tokens(prompt)
        await self.rate_limiter.wait_for_slot(estimated_tokens)
        
        try:
            async with self.session.post(url, json=request_data) as response:
                response.raise_for_status()
                
                async for line in response.content:
                    if line:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            data = line[6:]  # Remove 'data: ' prefix
                            try:
                                chunk = json.loads(data)
                                yield chunk
                            except json.JSONDecodeError:
                                continue
                                
        except Exception as e:
            self.logger.error(f"Error in Gemini streaming: {str(e)}")
            raise
    
    async def count_tokens(self, prompt: str, system_prompt: str = None) -> int:
        """Count tokens for the given prompt"""
        
        contents = []
        
        if system_prompt:
            contents.append({
                "parts": [{"text": system_prompt}]
            })
        
        contents.append({
            "parts": [{"text": prompt}]
        })
        
        request_data = {
            "contents": contents
        }
        
        model = self.config.get("model", "gemini-1.5-pro")
        url = f"{self.config['base_url']}/models/{model}:countTokens?key={self.api_key}"
        
        try:
            async with self.session.post(url, json=request_data) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("totalTokens", 0)
        except Exception as e:
            self.logger.error(f"Error counting tokens: {str(e)}")
            # Fallback to estimation
            return self.estimate_tokens(prompt + (system_prompt or ""))
    
    def get_available_models(self) -> list:
        """Get list of available Gemini models"""
        return [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.0-pro",
            "gemini-1.0-pro-vision"
        ]
    
    def validate_config(self) -> bool:
        """Validate Gemini-specific configuration"""
        if not super().validate_config():
            return False
        
        if not self.api_key:
            self.logger.error("GEMINI_API_KEY environment variable is not set")
            return False
        
        return True