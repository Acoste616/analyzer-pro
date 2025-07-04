import asyncio
import aiohttp
import json
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from ..config.settings import settings_manager
from ..utils.logger import get_logger


@dataclass
class LLMResponse:
    content: str
    usage: Dict[str, Any]
    model: str
    created_at: datetime
    processing_time: float
    metadata: Dict[str, Any]


@dataclass
class RateLimitInfo:
    requests_per_minute: int
    tokens_per_minute: Optional[int]
    current_requests: int = 0
    current_tokens: int = 0
    last_reset: datetime = None


class RateLimiter:
    def __init__(self, requests_per_minute: int, tokens_per_minute: Optional[int] = None):
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.request_timestamps: List[datetime] = []
        self.token_usage: List[tuple] = []  # (timestamp, tokens)
        self.lock = asyncio.Lock()
    
    async def acquire(self, estimated_tokens: int = 0) -> bool:
        async with self.lock:
            now = datetime.now()
            
            # Clean old requests (older than 1 minute)
            self.request_timestamps = [
                ts for ts in self.request_timestamps 
                if now - ts < timedelta(minutes=1)
            ]
            
            # Check request rate limit
            if len(self.request_timestamps) >= self.requests_per_minute:
                return False
            
            # Check token rate limit if specified
            if self.tokens_per_minute and estimated_tokens > 0:
                self.token_usage = [
                    (ts, tokens) for ts, tokens in self.token_usage
                    if now - ts < timedelta(minutes=1)
                ]
                
                current_tokens = sum(tokens for _, tokens in self.token_usage)
                if current_tokens + estimated_tokens > self.tokens_per_minute:
                    return False
            
            # Record the request
            self.request_timestamps.append(now)
            if estimated_tokens > 0:
                self.token_usage.append((now, estimated_tokens))
            
            return True
    
    async def wait_for_slot(self, estimated_tokens: int = 0) -> None:
        while not await self.acquire(estimated_tokens):
            await asyncio.sleep(1)


class BaseLLMClient(ABC):
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.settings = settings_manager.settings
        self.logger = get_logger(__name__)
        self.config = settings_manager.get_llm_config(provider_name)
        
        if not self.config:
            raise ValueError(f"No configuration found for provider: {provider_name}")
        
        # Initialize rate limiter
        rate_limit = self.config.get('rate_limit', {})
        self.rate_limiter = RateLimiter(
            requests_per_minute=rate_limit.get('requests_per_minute', 60),
            tokens_per_minute=rate_limit.get('tokens_per_minute')
        )
        
        # HTTP session
        self.session = None
        self.headers = self._get_headers()
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=100)
        timeout = aiohttp.ClientTimeout(total=self.config.get('timeout', 30))
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.headers
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @abstractmethod
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests"""
        pass
    
    @abstractmethod
    def _prepare_request(self, prompt: str, system_prompt: str = None, **kwargs) -> Dict[str, Any]:
        """Prepare request payload for the specific LLM provider"""
        pass
    
    @abstractmethod
    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Parse response from the specific LLM provider"""
        pass
    
    @abstractmethod
    def _get_endpoint_url(self) -> str:
        """Get the API endpoint URL"""
        pass
    
    async def generate(self, 
                      prompt: str, 
                      system_prompt: str = None,
                      **kwargs) -> LLMResponse:
        """Generate response from LLM"""
        
        # Estimate tokens for rate limiting (rough approximation)
        estimated_tokens = len(prompt.split()) * 1.3
        
        # Wait for rate limit slot
        await self.rate_limiter.wait_for_slot(int(estimated_tokens))
        
        start_time = time.time()
        
        try:
            # Prepare request
            request_data = self._prepare_request(prompt, system_prompt, **kwargs)
            
            # Make API request with retries
            response_data = await self._make_request_with_retry(request_data)
            
            # Parse response
            llm_response = self._parse_response(response_data)
            llm_response.processing_time = time.time() - start_time
            
            return llm_response
            
        except Exception as e:
            self.logger.error(f"Error generating response from {self.provider_name}: {str(e)}")
            raise
    
    async def _make_request_with_retry(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request with retry logic"""
        
        max_retries = self.config.get('retry_attempts', 3)
        retry_delay = self.config.get('retry_delay', 1.0)
        
        for attempt in range(max_retries):
            try:
                async with self.session.post(
                    self._get_endpoint_url(),
                    json=request_data
                ) as response:
                    
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:  # Rate limit
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (2 ** attempt))
                            continue
                        else:
                            raise Exception(f"Rate limit exceeded after {max_retries} attempts")
                    else:
                        response_text = await response.text()
                        raise Exception(f"HTTP {response.status}: {response_text}")
                        
            except aiohttp.ClientError as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    raise Exception(f"Network error after {max_retries} attempts: {str(e)}")
        
        raise Exception(f"Failed to get response after {max_retries} attempts")
    
    async def batch_generate(self, 
                           prompts: List[str],
                           system_prompt: str = None,
                           **kwargs) -> List[LLMResponse]:
        """Generate responses for multiple prompts"""
        
        tasks = []
        for prompt in prompts:
            task = self.generate(prompt, system_prompt, **kwargs)
            tasks.append(task)
        
        # Process with concurrency control
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
        
        async def process_with_semaphore(task):
            async with semaphore:
                return await task
        
        results = await asyncio.gather(
            *[process_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )
        
        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error in batch processing: {str(result)}")
            else:
                valid_results.append(result)
        
        return valid_results
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            'provider': self.provider_name,
            'model': self.config.get('model'),
            'max_tokens': self.config.get('max_tokens'),
            'temperature': self.config.get('temperature'),
            'base_url': self.config.get('base_url')
        }
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 characters per token on average)"""
        return len(text) // 4
    
    def validate_config(self) -> bool:
        """Validate client configuration"""
        required_fields = ['base_url', 'model', 'max_tokens']
        for field in required_fields:
            if field not in self.config:
                self.logger.error(f"Missing required config field: {field}")
                return False
        return True