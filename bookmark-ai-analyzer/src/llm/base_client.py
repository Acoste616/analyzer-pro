"""Base LLM client interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import asyncio
import time
from functools import wraps

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    """Standard response from LLM providers."""
    
    content: str
    model: str
    usage: Dict[str, int]  # tokens used, etc.
    metadata: Dict[str, Any]
    latency: float  # seconds
    cost: float  # estimated cost in USD
    
    @property
    def total_tokens(self) -> int:
        """Get total tokens used."""
        return self.usage.get("total_tokens", 0)


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, max_calls: int, time_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum calls allowed
            time_window: Time window in seconds (default 60)
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
        self._lock = asyncio.Lock()
        
    async def acquire(self):
        """Wait if necessary to respect rate limits."""
        async with self._lock:
            now = time.time()
            # Remove old calls outside the window
            self.calls = [t for t in self.calls if now - t < self.time_window]
            
            if len(self.calls) >= self.max_calls:
                # Wait until the oldest call is outside the window
                sleep_time = self.time_window - (now - self.calls[0]) + 0.1
                logger.debug(f"Rate limit reached, sleeping for {sleep_time:.1f}s")
                await asyncio.sleep(sleep_time)
                # Recursive call to recheck
                await self.acquire()
            else:
                self.calls.append(now)


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LLM client.
        
        Args:
            config: Provider-specific configuration
        """
        self.config = config
        self.api_key = config.get("api_key")
        self.model = config.get("model")
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.7)
        self.timeout = config.get("timeout", 30)
        self.max_retries = config.get("max_retries", 3)
        
        # Rate limiting
        rate_limit = config.get("rate_limit", 60)
        self.rate_limiter = RateLimiter(rate_limit)
        
        # Metrics
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.total_latency = 0.0
        
    @abstractmethod
    async def _make_request(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make the actual API request.
        
        Args:
            messages: Conversation messages
            **kwargs: Additional parameters
            
        Returns:
            Raw API response
        """
        pass
    
    @abstractmethod
    def _parse_response(self, response: Dict[str, Any]) -> LLMResponse:
        """
        Parse provider-specific response.
        
        Args:
            response: Raw API response
            
        Returns:
            Standardized LLMResponse
        """
        pass
    
    @abstractmethod
    def _calculate_cost(self, usage: Dict[str, int]) -> float:
        """
        Calculate cost for the request.
        
        Args:
            usage: Token usage information
            
        Returns:
            Estimated cost in USD
        """
        pass
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((Exception,)),
    )
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate completion for a prompt.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            **kwargs: Additional parameters
            
        Returns:
            LLM response
        """
        # Rate limiting
        await self.rate_limiter.acquire()
        
        # Prepare messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Track timing
        start_time = time.time()
        
        try:
            # Make request
            logger.debug(f"Making LLM request with {self.__class__.__name__}")
            response = await self._make_request(messages, **kwargs)
            
            # Parse response
            llm_response = self._parse_response(response)
            llm_response.latency = time.time() - start_time
            
            # Update metrics
            self.total_requests += 1
            self.total_tokens += llm_response.total_tokens
            self.total_cost += llm_response.cost
            self.total_latency += llm_response.latency
            
            logger.info(
                f"LLM request completed - Model: {llm_response.model}, "
                f"Tokens: {llm_response.total_tokens}, "
                f"Cost: ${llm_response.cost:.4f}, "
                f"Latency: {llm_response.latency:.2f}s"
            )
            
            return llm_response
            
        except Exception as e:
            logger.error(f"LLM request failed: {str(e)}")
            raise
    
    async def complete_batch(
        self,
        prompts: List[str],
        system_prompt: Optional[str] = None,
        max_concurrent: int = 5,
        **kwargs
    ) -> List[LLMResponse]:
        """
        Process multiple prompts concurrently.
        
        Args:
            prompts: List of prompts
            system_prompt: System instructions
            max_concurrent: Maximum concurrent requests
            **kwargs: Additional parameters
            
        Returns:
            List of responses
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_prompt(prompt: str) -> LLMResponse:
            async with semaphore:
                return await self.complete(prompt, system_prompt, **kwargs)
        
        tasks = [process_prompt(prompt) for prompt in prompts]
        return await asyncio.gather(*tasks)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics."""
        avg_latency = (
            self.total_latency / self.total_requests
            if self.total_requests > 0
            else 0
        )
        
        return {
            "provider": self.__class__.__name__,
            "model": self.model,
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "average_latency": avg_latency,
            "average_tokens_per_request": (
                self.total_tokens / self.total_requests
                if self.total_requests > 0
                else 0
            ),
        }
    
    def reset_metrics(self):
        """Reset client metrics."""
        self.total_requests = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.total_latency = 0.0


def rate_limit(max_calls: int, time_window: int = 60):
    """Decorator for rate limiting methods."""
    limiter = RateLimiter(max_calls, time_window)
    
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await limiter.acquire()
            return await func(*args, **kwargs)
        return wrapper
    return decorator