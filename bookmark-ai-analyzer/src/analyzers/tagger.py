"""Intelligent tagging system for content."""

import re
import json
from typing import Dict, List, Optional, Any, Set, Tuple
from collections import Counter, defaultdict
import asyncio

import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag

from ..llm import BaseLLMClient
from ..utils.logger import get_logger
from ..config import get_settings

logger = get_logger(__name__)

# Download required NLTK data
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
except Exception as e:
    logger.warning(f"Failed to download NLTK data: {e}")


class Tagger:
    """Generate intelligent tags for content."""
    
    # Tag categories
    TAG_TYPES = {
        "technical": {
            "patterns": [
                r'\b(?:API|SDK|framework|library|database|server|cloud|docker|kubernetes)\b',
                r'\b(?:python|javascript|typescript|java|go|rust|c\+\+|sql)\b',
                r'\b(?:react|vue|angular|django|flask|spring|node\.?js)\b',
            ],
            "prefix": "tech"
        },
        "difficulty": {
            "keywords": {
                "beginner": ["beginner", "introduction", "basics", "getting started", "101", "tutorial"],
                "intermediate": ["intermediate", "practical", "hands-on", "deep dive"],
                "advanced": ["advanced", "expert", "optimization", "architecture", "scale"]
            },
            "prefix": "level"
        },
        "content_type": {
            "keywords": {
                "tutorial": ["tutorial", "how to", "guide", "walkthrough"],
                "course": ["course", "bootcamp", "masterclass", "training"],
                "article": ["article", "blog", "post", "analysis"],
                "video": ["video", "watch", "youtube", "screencast"],
                "thread": ["thread", "🧵", "1/", "tweetstorm"]
            },
            "prefix": "type"
        },
        "time_investment": {
            "rules": {
                "quick": lambda content: len(content.split()) < 500,
                "medium": lambda content: 500 <= len(content.split()) < 2000,
                "long": lambda content: len(content.split()) >= 2000
            },
            "prefix": "time"
        }
    }
    
    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        """
        Initialize tagger.
        
        Args:
            llm_client: Optional LLM client for advanced tagging
        """
        self.llm_client = llm_client
        self.settings = get_settings()
        
        # Initialize stopwords
        try:
            self.stop_words = set(stopwords.words('english'))
        except:
            # Fallback to basic stopwords if NLTK data not available
            self.stop_words = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
                'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that'
            }
    
    async def generate_tags(
        self,
        content_item: Dict[str, Any],
        max_tags: int = 10,
        use_llm: bool = True,
        include_meta_tags: bool = True
    ) -> Dict[str, Any]:
        """
        Generate tags for content.
        
        Args:
            content_item: Content to tag
            max_tags: Maximum number of tags
            use_llm: Whether to use LLM for tag generation
            include_meta_tags: Include metadata-based tags
            
        Returns:
            Tagging results
        """
        # Extract text for tagging
        text = self._extract_taggable_text(content_item)
        
        # Generate tags using different methods
        keyword_tags = self._extract_keyword_tags(text)
        entity_tags = self._extract_entity_tags(text)
        meta_tags = self._generate_meta_tags(content_item) if include_meta_tags else []
        
        # LLM-based tags if enabled
        llm_tags = []
        if use_llm and self.llm_client:
            llm_tags = await self._generate_llm_tags(content_item)
        
        # Combine and rank tags
        all_tags = self._combine_and_rank_tags(
            keyword_tags,
            entity_tags,
            meta_tags,
            llm_tags,
            max_tags
        )
        
        # Categorize tags
        categorized_tags = self._categorize_tags(all_tags)
        
        return {
            'tags': all_tags[:max_tags],
            'categorized_tags': categorized_tags,
            'tag_sources': {
                'keywords': keyword_tags[:5],
                'entities': entity_tags[:5],
                'metadata': meta_tags[:5],
                'llm': llm_tags[:5]
            },
            'tag_count': len(all_tags)
        }
    
    def _extract_taggable_text(self, content_item: Dict[str, Any]) -> str:
        """Extract relevant text for tagging."""
        parts = []
        
        # Add title
        if title := content_item.get('title'):
            parts.append(title)
        
        # Add content
        if content := content_item.get('content'):
            parts.append(content)
        
        # Add description
        if description := content_item.get('description'):
            parts.append(description)
        
        return ' '.join(parts)
    
    def _extract_keyword_tags(self, text: str) -> List[str]:
        """Extract keyword-based tags."""
        # Tokenize and clean
        try:
            tokens = word_tokenize(text.lower())
        except:
            # Fallback to simple split if NLTK fails
            tokens = text.lower().split()
        
        # Remove stopwords and short tokens
        keywords = [
            token for token in tokens
            if token not in self.stop_words
            and len(token) > 2
            and token.isalnum()
        ]
        
        # Get POS tags for better filtering
        try:
            pos_tags = pos_tag(keywords)
            # Keep only nouns and verbs
            keywords = [
                word for word, pos in pos_tags
                if pos.startswith(('NN', 'VB'))
            ]
        except:
            pass
        
        # Count frequencies
        keyword_freq = Counter(keywords)
        
        # Get top keywords
        top_keywords = [
            keyword for keyword, _ in keyword_freq.most_common(20)
        ]
        
        return top_keywords
    
    def _extract_entity_tags(self, text: str) -> List[str]:
        """Extract named entities and technical terms."""
        entities = []
        
        # Technical terms
        tech_patterns = [
            r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b',  # CamelCase
            r'\b[A-Z]{2,}\b',  # Acronyms
            r'\b\w+\.js\b',  # .js frameworks
            r'\b\w+\.py\b',  # Python files
            r'#\w+',  # Hashtags
            r'@\w+',  # Mentions
        ]
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, text)
            entities.extend(matches)
        
        # Programming languages and frameworks
        tech_terms = {
            'python', 'javascript', 'typescript', 'react', 'vue', 'angular',
            'django', 'flask', 'nodejs', 'docker', 'kubernetes', 'aws',
            'gcp', 'azure', 'mongodb', 'postgresql', 'redis', 'graphql',
            'rest', 'api', 'machine learning', 'deep learning', 'ai', 'ml'
        }
        
        text_lower = text.lower()
        for term in tech_terms:
            if term in text_lower:
                entities.append(term)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_entities = []
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower not in seen:
                seen.add(entity_lower)
                unique_entities.append(entity)
        
        return unique_entities
    
    def _generate_meta_tags(self, content_item: Dict[str, Any]) -> List[str]:
        """Generate metadata-based tags."""
        meta_tags = []
        
        # Content type tags
        content_type = content_item.get('type', '')
        if content_type:
            meta_tags.append(f"type:{content_type}")
        
        # Difficulty level
        content = content_item.get('content', '')
        for level, keywords in self.TAG_TYPES['difficulty']['keywords'].items():
            if any(keyword in content.lower() for keyword in keywords):
                meta_tags.append(f"level:{level}")
                break
        
        # Time investment
        for time_cat, rule in self.TAG_TYPES['time_investment']['rules'].items():
            if rule(content):
                meta_tags.append(f"time:{time_cat}")
                break
        
        # Platform/source tags
        if url := content_item.get('url', ''):
            if 'youtube.com' in url:
                meta_tags.append('platform:youtube')
            elif 'twitter.com' in url or 'x.com' in url:
                meta_tags.append('platform:twitter')
        
        # Author tags
        if author := content_item.get('author'):
            meta_tags.append(f"author:{author}")
        
        # Category tags
        if category := content_item.get('category'):
            meta_tags.append(f"category:{category.lower()}")
        
        return meta_tags
    
    async def _generate_llm_tags(self, content_item: Dict[str, Any]) -> List[str]:
        """Generate tags using LLM."""
        if not self.llm_client:
            return []
        
        prompt = f"""Generate relevant tags for this content.

Content type: {content_item.get('type', 'unknown')}
Title: {content_item.get('title', 'N/A')}
Content preview: {content_item.get('content', '')[:500]}

Generate:
1. 5-10 specific, relevant tags
2. Include technical terms if applicable
3. Include difficulty level
4. Include content format
5. Make tags actionable and searchable

Format: Return only a JSON array of tags.
Example: ["python", "web-scraping", "tutorial", "beginner-friendly", "beautifulsoup"]"""
        
        try:
            response = await self.llm_client.complete(prompt)
            tags = json.loads(response.content)
            if isinstance(tags, list):
                return tags
        except Exception as e:
            logger.error(f"LLM tag generation failed: {e}")
        
        return []
    
    def _combine_and_rank_tags(
        self,
        keyword_tags: List[str],
        entity_tags: List[str],
        meta_tags: List[str],
        llm_tags: List[str],
        max_tags: int
    ) -> List[str]:
        """Combine and rank tags from different sources."""
        # Score tags based on source and frequency
        tag_scores = defaultdict(float)
        
        # Add keyword tags (weight: 0.3)
        for i, tag in enumerate(keyword_tags[:10]):
            tag_scores[tag.lower()] += (10 - i) * 0.3
        
        # Add entity tags (weight: 0.4)
        for i, tag in enumerate(entity_tags[:10]):
            tag_scores[tag.lower()] += (10 - i) * 0.4
        
        # Add meta tags (weight: 0.2)
        for tag in meta_tags:
            tag_scores[tag.lower()] += 5 * 0.2
        
        # Add LLM tags (weight: 0.3)
        for i, tag in enumerate(llm_tags[:10]):
            tag_scores[tag.lower()] += (10 - i) * 0.3
        
        # Sort by score
        sorted_tags = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Get unique tags preserving original case
        final_tags = []
        seen_lower = set()
        
        # First add all tags from all sources to get original case
        all_source_tags = keyword_tags + entity_tags + meta_tags + llm_tags
        tag_case_map = {tag.lower(): tag for tag in all_source_tags}
        
        for tag_lower, score in sorted_tags:
            if tag_lower not in seen_lower:
                seen_lower.add(tag_lower)
                # Use original case if available
                original_tag = tag_case_map.get(tag_lower, tag_lower)
                final_tags.append(original_tag)
                
                if len(final_tags) >= max_tags:
                    break
        
        return final_tags
    
    def _categorize_tags(self, tags: List[str]) -> Dict[str, List[str]]:
        """Categorize tags by type."""
        categorized = {
            'technical': [],
            'difficulty': [],
            'content_type': [],
            'time': [],
            'platform': [],
            'author': [],
            'category': [],
            'general': []
        }
        
        for tag in tags:
            categorized_flag = False
            
            # Check for prefixed tags
            if ':' in tag:
                prefix, value = tag.split(':', 1)
                if prefix in categorized:
                    categorized[prefix].append(value)
                    categorized_flag = True
            
            # Check technical patterns
            if not categorized_flag:
                for pattern in self.TAG_TYPES['technical']['patterns']:
                    if re.match(pattern, tag, re.IGNORECASE):
                        categorized['technical'].append(tag)
                        categorized_flag = True
                        break
            
            # Check difficulty keywords
            if not categorized_flag:
                for level, keywords in self.TAG_TYPES['difficulty']['keywords'].items():
                    if any(keyword in tag.lower() for keyword in keywords):
                        categorized['difficulty'].append(tag)
                        categorized_flag = True
                        break
            
            # Default to general
            if not categorized_flag:
                categorized['general'].append(tag)
        
        # Remove empty categories
        return {k: v for k, v in categorized.items() if v}
    
    async def batch_generate_tags(
        self,
        content_items: List[Dict[str, Any]],
        max_tags: int = 10,
        use_llm: bool = True,
        max_concurrent: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Generate tags for multiple content items.
        
        Args:
            content_items: List of content to tag
            max_tags: Maximum tags per item
            use_llm: Whether to use LLM
            max_concurrent: Maximum concurrent operations
            
        Returns:
            List of tagging results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def tag_with_semaphore(item):
            async with semaphore:
                return await self.generate_tags(item, max_tags, use_llm)
        
        tasks = [tag_with_semaphore(item) for item in content_items]
        return await asyncio.gather(*tasks)
    
    def get_tag_statistics(
        self,
        tagging_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate statistics from tagging results.
        
        Args:
            tagging_results: List of tagging results
            
        Returns:
            Tag statistics
        """
        all_tags = []
        categorized_counts = defaultdict(int)
        
        for result in tagging_results:
            all_tags.extend(result.get('tags', []))
            
            # Count categorized tags
            for category, tags in result.get('categorized_tags', {}).items():
                categorized_counts[category] += len(tags)
        
        # Count tag frequencies
        tag_freq = Counter(all_tags)
        
        return {
            'total_unique_tags': len(set(all_tags)),
            'total_tags': len(all_tags),
            'average_tags_per_item': len(all_tags) / len(tagging_results) if tagging_results else 0,
            'most_common_tags': tag_freq.most_common(20),
            'category_distribution': dict(categorized_counts),
            'tag_frequency_distribution': {
                'single_use': sum(1 for count in tag_freq.values() if count == 1),
                'moderate_use': sum(1 for count in tag_freq.values() if 2 <= count <= 5),
                'frequent_use': sum(1 for count in tag_freq.values() if count > 5)
            }
        }
    
    def suggest_tag_consolidation(
        self,
        tag_statistics: Dict[str, Any]
    ) -> List[Tuple[str, List[str]]]:
        """
        Suggest tag consolidations based on similarity.
        
        Args:
            tag_statistics: Tag statistics
            
        Returns:
            List of (canonical_tag, similar_tags) tuples
        """
        # In a real implementation, would use string similarity algorithms
        # For now, return empty list
        return []