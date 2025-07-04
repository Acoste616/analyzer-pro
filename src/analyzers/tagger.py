import asyncio
import json
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
from collections import Counter

from ..config.settings import settings_manager
from ..utils.logger import get_logger
from ..llm.grok_client import GrokClient
from ..llm.claude_client import ClaudeClient
from ..llm.gemini_client import GeminiClient


@dataclass
class TagResult:
    tags: List[str]
    tag_confidence: Dict[str, float]
    tag_categories: Dict[str, str]
    tag_hierarchy: Dict[str, List[str]]
    tagging_metadata: Dict[str, Any]


class Tagger:
    def __init__(self):
        self.settings = settings_manager.settings
        self.logger = get_logger(__name__)
        self.llm_configs = settings_manager.llm_configs
        
        # Predefined tag categories
        self.tag_categories = {
            "technology": ["programming", "software", "development", "coding", "framework", "library", "tool", "api", "database"],
            "language": ["python", "javascript", "java", "c++", "go", "rust", "typescript", "php", "ruby", "swift"],
            "platform": ["web", "mobile", "desktop", "cloud", "aws", "azure", "gcp", "docker", "kubernetes"],
            "methodology": ["agile", "devops", "testing", "automation", "ci/cd", "deployment", "monitoring"],
            "domain": ["fintech", "healthcare", "ecommerce", "gaming", "education", "automotive", "IoT"],
            "skill_level": ["beginner", "intermediate", "advanced", "expert", "tutorial", "guide"],
            "content_type": ["article", "tutorial", "documentation", "news", "opinion", "research", "case-study"],
            "business": ["startup", "enterprise", "saas", "b2b", "b2c", "marketing", "sales", "strategy"]
        }
        
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
    
    async def generate_tags(self, content: str, preferred_provider: str = None) -> List[str]:
        """
        Generate tags for content using LLM
        
        Args:
            content: Text content to tag
            preferred_provider: Preferred LLM provider
            
        Returns:
            List of tags
        """
        tag_result = await self.generate_tags_detailed(content, preferred_provider)
        return tag_result.tags
    
    async def generate_tags_detailed(self, content: str, preferred_provider: str = None) -> TagResult:
        """
        Generate detailed tags for content
        
        Args:
            content: Text content to tag
            preferred_provider: Preferred LLM provider
            
        Returns:
            TagResult object with detailed tagging information
        """
        if not content or not content.strip():
            raise ValueError("Content cannot be empty")
        
        # Choose provider
        provider = preferred_provider or self.settings.analysis.default_llm_provider
        if provider not in self.clients:
            provider = next(iter(self.clients.keys()))
        
        client = self.clients[provider]
        
        # Get tagging prompts
        tagging_prompts = settings_manager.get_analysis_prompt("tagging")
        if not tagging_prompts:
            raise ValueError("Tagging prompts not found in configuration")
        
        # Prepare prompt
        user_prompt = tagging_prompts["user_prompt"].format(content=content)
        system_prompt = tagging_prompts["system_prompt"]
        
        try:
            async with client:
                # Generate tagging response
                response = await client.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.3,  # Lower temperature for more consistent tagging
                    max_tokens=800
                )
                
                # Parse the response
                tag_result = self._parse_tagging_response(response.content, content)
                
                # Add metadata
                tag_result.tagging_metadata = {
                    "provider": provider,
                    "model": response.model,
                    "processing_time": response.processing_time,
                    "tagged_at": datetime.now().isoformat(),
                    "prompt_tokens": response.usage.get("prompt_tokens", 0),
                    "completion_tokens": response.usage.get("completion_tokens", 0),
                    "total_tokens": response.usage.get("total_tokens", 0)
                }
                
                return tag_result
                
        except Exception as e:
            self.logger.error(f"Error generating tags with {provider}: {str(e)}")
            # Return fallback tagging
            return self._fallback_tagging(content)
    
    def _parse_tagging_response(self, response_content: str, original_content: str) -> TagResult:
        """Parse LLM response into structured tag result"""
        
        # Initialize default values
        tags = []
        tag_confidence = {}
        
        try:
            # Try to parse structured response
            lines = response_content.strip().split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Identify sections
                if line.startswith('**Tags**') or line.startswith('- **Tags**'):
                    current_section = 'tags'
                elif line.startswith('**Tag Confidence**') or line.startswith('- **Tag Confidence**'):
                    current_section = 'confidence'
                elif line.startswith('- ') and current_section == 'tags':
                    # Extract tag
                    tag = line[2:].strip()
                    if tag:
                        tags.append(tag)
                elif current_section == 'confidence' and ':' in line:
                    # Extract confidence score
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        tag = parts[0].strip()
                        try:
                            confidence = float(parts[1].strip().split()[0])
                            tag_confidence[tag] = confidence
                        except:
                            tag_confidence[tag] = 5.0
            
            # If no tags found, try alternative parsing
            if not tags:
                # Look for comma-separated tags
                if ',' in response_content:
                    potential_tags = [tag.strip() for tag in response_content.split(',')]
                    tags = [tag for tag in potential_tags if tag and len(tag) > 2]
                else:
                    # Look for individual lines as tags
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('**') and not line.startswith('-'):
                            if len(line.split()) <= 3:  # Likely a tag
                                tags.append(line)
            
            # Clean and validate tags
            tags = self._clean_tags(tags)
            
            # If still no tags, use fallback
            if not tags:
                return self._fallback_tagging(original_content)
            
        except Exception as e:
            self.logger.warning(f"Error parsing tagging response: {str(e)}")
            return self._fallback_tagging(original_content)
        
        # Categorize tags
        tag_categories = self._categorize_tags(tags)
        
        # Build tag hierarchy
        tag_hierarchy = self._build_tag_hierarchy(tags)
        
        # Set default confidence for tags without confidence scores
        for tag in tags:
            if tag not in tag_confidence:
                tag_confidence[tag] = 7.0  # Default confidence
        
        return TagResult(
            tags=tags[:15],  # Limit to top 15 tags
            tag_confidence=tag_confidence,
            tag_categories=tag_categories,
            tag_hierarchy=tag_hierarchy,
            tagging_metadata={}
        )
    
    def _clean_tags(self, tags: List[str]) -> List[str]:
        """Clean and normalize tags"""
        cleaned_tags = []
        
        for tag in tags:
            # Remove special characters and normalize
            tag = re.sub(r'[^\w\s-]', '', tag).strip()
            
            # Convert to lowercase
            tag = tag.lower()
            
            # Skip very short or very long tags
            if len(tag) < 2 or len(tag) > 30:
                continue
            
            # Skip common stop words
            stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'a', 'an'}
            if tag in stop_words:
                continue
            
            # Replace spaces with hyphens for multi-word tags
            tag = tag.replace(' ', '-')
            
            cleaned_tags.append(tag)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in cleaned_tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
        
        return unique_tags
    
    def _categorize_tags(self, tags: List[str]) -> Dict[str, str]:
        """Categorize tags based on predefined categories"""
        tag_categories = {}
        
        for tag in tags:
            tag_lower = tag.lower()
            category_found = False
            
            for category, keywords in self.tag_categories.items():
                for keyword in keywords:
                    if keyword in tag_lower or tag_lower in keyword:
                        tag_categories[tag] = category
                        category_found = True
                        break
                
                if category_found:
                    break
            
            if not category_found:
                tag_categories[tag] = "general"
        
        return tag_categories
    
    def _build_tag_hierarchy(self, tags: List[str]) -> Dict[str, List[str]]:
        """Build hierarchical relationships between tags"""
        tag_hierarchy = {}
        
        # Group tags by category
        categories = {}
        for tag in tags:
            tag_lower = tag.lower()
            
            # Find category for this tag
            for category, keywords in self.tag_categories.items():
                for keyword in keywords:
                    if keyword in tag_lower or tag_lower in keyword:
                        if category not in categories:
                            categories[category] = []
                        categories[category].append(tag)
                        break
        
        # Build hierarchy
        for category, category_tags in categories.items():
            if len(category_tags) > 1:
                # Find the most general tag in the category
                general_tag = min(category_tags, key=len)
                specific_tags = [tag for tag in category_tags if tag != general_tag]
                
                if specific_tags:
                    tag_hierarchy[general_tag] = specific_tags
        
        return tag_hierarchy
    
    def _fallback_tagging(self, content: str) -> TagResult:
        """Fallback tagging using keyword extraction"""
        
        # Extract potential tags using various methods
        tags = []
        
        # Method 1: Extract capitalized words (potential proper nouns)
        capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', content)
        tags.extend(capitalized_words)
        
        # Method 2: Extract technical terms
        technical_terms = []
        for category_tags in self.tag_categories.values():
            for term in category_tags:
                if term.lower() in content.lower():
                    technical_terms.append(term)
        tags.extend(technical_terms)
        
        # Method 3: Extract URLs and extract domain names
        urls = re.findall(r'https?://[^\s]+', content)
        for url in urls:
            domain = re.findall(r'://([^/]+)', url)
            if domain:
                tags.append(domain[0].split('.')[0])
        
        # Method 4: Extract hashtags if present
        hashtags = re.findall(r'#(\w+)', content)
        tags.extend(hashtags)
        
        # Clean and limit tags
        tags = self._clean_tags(tags)
        tags = tags[:10]  # Limit to top 10
        
        # Generate confidence scores
        tag_confidence = {}
        for tag in tags:
            # Higher confidence for technical terms
            if any(tag.lower() in category_tags for category_tags in self.tag_categories.values()):
                tag_confidence[tag] = 8.0
            else:
                tag_confidence[tag] = 5.0
        
        # Categorize tags
        tag_categories = self._categorize_tags(tags)
        
        # Build tag hierarchy
        tag_hierarchy = self._build_tag_hierarchy(tags)
        
        return TagResult(
            tags=tags,
            tag_confidence=tag_confidence,
            tag_categories=tag_categories,
            tag_hierarchy=tag_hierarchy,
            tagging_metadata={"method": "fallback_keyword_extraction"}
        )
    
    async def generate_tags_batch(self, 
                                contents: List[str],
                                preferred_provider: str = None) -> List[TagResult]:
        """Generate tags for multiple contents in batch"""
        
        # Process with concurrency control
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent tagging operations
        
        async def tag_with_semaphore(content):
            async with semaphore:
                return await self.generate_tags_detailed(content, preferred_provider)
        
        tasks = [tag_with_semaphore(content) for content in contents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error in batch tagging: {str(result)}")
                # Add a default result for failed tagging
                valid_results.append(TagResult(
                    tags=[],
                    tag_confidence={},
                    tag_categories={},
                    tag_hierarchy={},
                    tagging_metadata={"error": str(result)}
                ))
            else:
                valid_results.append(result)
        
        return valid_results
    
    def get_tag_statistics(self, results: List[TagResult]) -> Dict[str, Any]:
        """Get statistics from tagging results"""
        
        if not results:
            return {}
        
        # Collect all tags
        all_tags = []
        for result in results:
            all_tags.extend(result.tags)
        
        # Count tag frequencies
        tag_counts = Counter(all_tags)
        
        # Count tags by category
        category_counts = {}
        for result in results:
            for tag, category in result.tag_categories.items():
                category_counts[category] = category_counts.get(category, 0) + 1
        
        # Calculate average confidence
        all_confidence_scores = []
        for result in results:
            all_confidence_scores.extend(result.tag_confidence.values())
        
        avg_confidence = sum(all_confidence_scores) / len(all_confidence_scores) if all_confidence_scores else 0
        
        # Calculate average tags per item
        avg_tags_per_item = len(all_tags) / len(results) if results else 0
        
        return {
            "total_tagged": len(results),
            "total_unique_tags": len(tag_counts),
            "most_common_tags": dict(tag_counts.most_common(20)),
            "tag_category_distribution": dict(sorted(category_counts.items(), key=lambda x: x[1], reverse=True)),
            "average_confidence": round(avg_confidence, 2),
            "average_tags_per_item": round(avg_tags_per_item, 2),
            "tagging_timestamp": datetime.now().isoformat()
        }
    
    def suggest_related_tags(self, tags: List[str]) -> List[str]:
        """Suggest related tags based on input tags"""
        
        related_tags = set()
        
        for tag in tags:
            tag_lower = tag.lower()
            
            # Find related tags in the same category
            for category, keywords in self.tag_categories.items():
                if any(keyword in tag_lower or tag_lower in keyword for keyword in keywords):
                    # Add other keywords from the same category
                    related_tags.update(keywords)
        
        # Remove original tags
        related_tags = related_tags - set(tag.lower() for tag in tags)
        
        return list(related_tags)[:10]  # Return top 10 suggestions
    
    def merge_similar_tags(self, tags: List[str], similarity_threshold: float = 0.8) -> List[str]:
        """Merge similar tags based on string similarity"""
        
        from difflib import SequenceMatcher
        
        def similarity(a, b):
            return SequenceMatcher(None, a.lower(), b.lower()).ratio()
        
        merged_tags = []
        processed = set()
        
        for tag in tags:
            if tag in processed:
                continue
            
            # Find similar tags
            similar_tags = [tag]
            for other_tag in tags:
                if other_tag != tag and other_tag not in processed:
                    if similarity(tag, other_tag) >= similarity_threshold:
                        similar_tags.append(other_tag)
                        processed.add(other_tag)
            
            # Use the shortest tag as the representative
            representative_tag = min(similar_tags, key=len)
            merged_tags.append(representative_tag)
            processed.add(tag)
        
        return merged_tags
    
    def get_tag_categories(self) -> Dict[str, List[str]]:
        """Get all predefined tag categories"""
        return self.tag_categories.copy()
    
    def add_tag_category(self, category: str, keywords: List[str]):
        """Add a new tag category"""
        self.tag_categories[category] = keywords
    
    def update_tag_category(self, category: str, keywords: List[str]):
        """Update an existing tag category"""
        if category in self.tag_categories:
            self.tag_categories[category].extend(keywords)
            # Remove duplicates
            self.tag_categories[category] = list(set(self.tag_categories[category]))