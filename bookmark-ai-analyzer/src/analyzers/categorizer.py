"""Content categorization module using hierarchical categories."""

import json
from typing import Dict, List, Optional, Any, Tuple, Set
from collections import defaultdict
import asyncio

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from ..llm import BaseLLMClient
from ..utils.logger import get_logger
from ..config import get_settings

logger = get_logger(__name__)


class Categorizer:
    """Categorize content into hierarchical categories."""
    
    # Hierarchical category structure
    CATEGORY_HIERARCHY = {
        "Programming": {
            "subcategories": [
                "Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C++",
                "Web Development", "Mobile Development", "DevOps", "Cloud Computing",
                "Databases", "APIs", "Microservices", "System Design"
            ],
            "keywords": [
                "code", "programming", "development", "software", "algorithm",
                "framework", "library", "debug", "deploy", "git", "docker"
            ]
        },
        "AI/ML": {
            "subcategories": [
                "Machine Learning", "Deep Learning", "NLP", "Computer Vision",
                "LLMs", "Neural Networks", "Data Science", "MLOps",
                "Reinforcement Learning", "AI Ethics", "Generative AI"
            ],
            "keywords": [
                "ai", "ml", "machine learning", "deep learning", "neural",
                "model", "training", "dataset", "tensorflow", "pytorch",
                "transformer", "gpt", "llm", "artificial intelligence"
            ]
        },
        "Business": {
            "subcategories": [
                "Startups", "Marketing", "Sales", "Strategy", "Leadership",
                "Product Management", "Finance", "Entrepreneurship",
                "Growth Hacking", "B2B", "SaaS", "Venture Capital"
            ],
            "keywords": [
                "business", "startup", "marketing", "sales", "revenue",
                "growth", "strategy", "management", "leadership", "entrepreneur",
                "investor", "funding", "customer", "product"
            ]
        },
        "Technology": {
            "subcategories": [
                "Blockchain", "Crypto", "Web3", "Security", "Privacy",
                "Hardware", "IoT", "AR/VR", "Quantum Computing",
                "5G", "Edge Computing", "Tech News"
            ],
            "keywords": [
                "technology", "tech", "blockchain", "crypto", "bitcoin",
                "security", "privacy", "hardware", "innovation", "digital",
                "web3", "metaverse", "nft"
            ]
        },
        "Education": {
            "subcategories": [
                "Online Courses", "Tutorials", "Books", "Research Papers",
                "Certifications", "Workshops", "Bootcamps", "MOOCs",
                "Study Techniques", "Academic", "E-learning"
            ],
            "keywords": [
                "learn", "education", "course", "tutorial", "study",
                "teach", "lesson", "workshop", "certification", "training",
                "academic", "research", "knowledge"
            ]
        },
        "Lifestyle": {
            "subcategories": [
                "Productivity", "Health", "Fitness", "Mental Health",
                "Personal Finance", "Career Development", "Remote Work",
                "Work-Life Balance", "Habits", "Self-Improvement"
            ],
            "keywords": [
                "productivity", "health", "fitness", "wellness", "mindfulness",
                "career", "remote", "balance", "habit", "routine",
                "personal", "development", "growth"
            ]
        },
        "Science": {
            "subcategories": [
                "Physics", "Biology", "Chemistry", "Space", "Medicine",
                "Environment", "Climate", "Research", "Innovation",
                "Biotechnology", "Neuroscience"
            ],
            "keywords": [
                "science", "research", "study", "experiment", "discovery",
                "physics", "biology", "chemistry", "space", "medical",
                "climate", "environment", "scientific"
            ]
        }
    }
    
    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        """
        Initialize categorizer.
        
        Args:
            llm_client: Optional LLM client for advanced categorization
        """
        self.llm_client = llm_client
        self.settings = get_settings()
        
        # Initialize TF-IDF vectorizer for keyword matching
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        
        # Prepare category keywords for vectorization
        self._prepare_category_vectors()
        
    def _prepare_category_vectors(self):
        """Prepare TF-IDF vectors for categories."""
        category_texts = []
        self.category_names = []
        
        for category, info in self.CATEGORY_HIERARCHY.items():
            # Combine category name, subcategories, and keywords
            text = f"{category} " + " ".join(info["subcategories"]) + " " + " ".join(info["keywords"])
            category_texts.append(text)
            self.category_names.append(category)
        
        # Fit vectorizer on category texts
        self.category_vectors = self.vectorizer.fit_transform(category_texts)
    
    async def categorize_content(
        self,
        content_item: Dict[str, Any],
        use_llm: bool = True,
        confidence_threshold: float = 0.3
    ) -> Dict[str, Any]:
        """
        Categorize a content item.
        
        Args:
            content_item: Content to categorize
            use_llm: Whether to use LLM for enhanced categorization
            confidence_threshold: Minimum confidence for category assignment
            
        Returns:
            Categorization results
        """
        # Extract text for categorization
        text = self._extract_categorizable_text(content_item)
        
        # Rule-based categorization
        rule_based_results = self._rule_based_categorization(text)
        
        # TF-IDF based categorization
        tfidf_results = self._tfidf_categorization(text)
        
        # LLM-based categorization if enabled
        llm_results = {}
        if use_llm and self.llm_client:
            llm_results = await self._llm_categorization(content_item)
        
        # Combine results
        final_categories = self._combine_categorization_results(
            rule_based_results,
            tfidf_results,
            llm_results,
            confidence_threshold
        )
        
        return {
            'primary_category': final_categories['primary'],
            'subcategories': final_categories['subcategories'],
            'confidence_scores': final_categories['scores'],
            'all_detected_categories': final_categories['all_detected'],
            'method_results': {
                'rule_based': rule_based_results,
                'tfidf': tfidf_results,
                'llm': llm_results
            }
        }
    
    def _extract_categorizable_text(self, content_item: Dict[str, Any]) -> str:
        """Extract relevant text for categorization."""
        parts = []
        
        # Add title if available
        if title := content_item.get('title'):
            parts.append(title)
        
        # Add content
        if content := content_item.get('content'):
            parts.append(content[:2000])  # Limit length
        
        # Add description for videos
        if description := content_item.get('description'):
            parts.append(description)
        
        # Add tags and hashtags
        metadata = content_item.get('metadata', {})
        if hashtags := metadata.get('hashtags'):
            parts.append(' '.join(f"#{tag}" for tag in hashtags))
        
        return ' '.join(parts)
    
    def _rule_based_categorization(self, text: str) -> Dict[str, float]:
        """Simple rule-based categorization using keywords."""
        text_lower = text.lower()
        scores = {}
        
        for category, info in self.CATEGORY_HIERARCHY.items():
            score = 0.0
            keyword_count = 0
            
            # Check keywords
            for keyword in info['keywords']:
                if keyword in text_lower:
                    keyword_count += 1
            
            # Check subcategories
            for subcat in info['subcategories']:
                if subcat.lower() in text_lower:
                    keyword_count += 2  # Subcategories have higher weight
            
            # Calculate score
            if keyword_count > 0:
                score = min(1.0, keyword_count / 10)
                scores[category] = score
        
        return scores
    
    def _tfidf_categorization(self, text: str) -> Dict[str, float]:
        """TF-IDF based categorization."""
        try:
            # Transform text to vector
            text_vector = self.vectorizer.transform([text])
            
            # Calculate similarities
            similarities = cosine_similarity(text_vector, self.category_vectors)[0]
            
            # Create scores dictionary
            scores = {}
            for i, category in enumerate(self.category_names):
                if similarities[i] > 0:
                    scores[category] = float(similarities[i])
            
            return scores
            
        except Exception as e:
            logger.error(f"TF-IDF categorization failed: {e}")
            return {}
    
    async def _llm_categorization(self, content_item: Dict[str, Any]) -> Dict[str, Any]:
        """LLM-based categorization for better accuracy."""
        if not self.llm_client:
            return {}
        
        # Prepare categories list
        categories_list = list(self.CATEGORY_HIERARCHY.keys())
        
        prompt = f"""Categorize this content into appropriate categories.

Available categories: {', '.join(categories_list)}

Content type: {content_item.get('type', 'unknown')}
Title: {content_item.get('title', 'N/A')}
Content: {content_item.get('content', '')[:1000]}

Provide:
1. Primary category (must be from the list)
2. Up to 3 subcategories
3. Confidence score for each (0-1)
4. Reasoning for categorization

Format as JSON:
{{
    "primary_category": "...",
    "subcategories": ["...", "..."],
    "confidence_scores": {{"category": score}},
    "reasoning": "..."
}}"""
        
        try:
            response = await self.llm_client.complete(prompt)
            return json.loads(response.content)
        except Exception as e:
            logger.error(f"LLM categorization failed: {e}")
            return {}
    
    def _combine_categorization_results(
        self,
        rule_based: Dict[str, float],
        tfidf: Dict[str, float],
        llm: Dict[str, Any],
        threshold: float
    ) -> Dict[str, Any]:
        """Combine results from different categorization methods."""
        # Aggregate scores
        all_scores = defaultdict(float)
        
        # Add rule-based scores (weight: 0.3)
        for category, score in rule_based.items():
            all_scores[category] += score * 0.3
        
        # Add TF-IDF scores (weight: 0.3)
        for category, score in tfidf.items():
            all_scores[category] += score * 0.3
        
        # Add LLM scores if available (weight: 0.4)
        if llm and 'confidence_scores' in llm:
            for category, score in llm['confidence_scores'].items():
                if category in self.CATEGORY_HIERARCHY:
                    all_scores[category] += score * 0.4
        
        # Sort by score
        sorted_categories = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Determine primary category
        primary_category = sorted_categories[0][0] if sorted_categories and sorted_categories[0][1] >= threshold else "Other"
        
        # Get subcategories
        subcategories = []
        if llm and 'subcategories' in llm:
            subcategories = llm['subcategories']
        else:
            # Extract from category hierarchy
            if primary_category in self.CATEGORY_HIERARCHY:
                # Find most relevant subcategories based on content
                # This is simplified - in production would use more sophisticated matching
                subcategories = self.CATEGORY_HIERARCHY[primary_category]['subcategories'][:3]
        
        return {
            'primary': primary_category,
            'subcategories': subcategories,
            'scores': dict(all_scores),
            'all_detected': [cat for cat, score in sorted_categories if score >= threshold]
        }
    
    async def batch_categorize(
        self,
        content_items: List[Dict[str, Any]],
        use_llm: bool = True,
        max_concurrent: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Categorize multiple content items.
        
        Args:
            content_items: List of content to categorize
            use_llm: Whether to use LLM
            max_concurrent: Maximum concurrent categorizations
            
        Returns:
            List of categorization results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def categorize_with_semaphore(item):
            async with semaphore:
                return await self.categorize_content(item, use_llm)
        
        tasks = [categorize_with_semaphore(item) for item in content_items]
        return await asyncio.gather(*tasks)
    
    def get_category_statistics(
        self,
        categorization_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate statistics from categorization results.
        
        Args:
            categorization_results: List of categorization results
            
        Returns:
            Category statistics
        """
        stats = {
            'total_items': len(categorization_results),
            'category_distribution': defaultdict(int),
            'subcategory_distribution': defaultdict(int),
            'average_confidence': {},
            'uncategorized_count': 0
        }
        
        confidence_sums = defaultdict(float)
        confidence_counts = defaultdict(int)
        
        for result in categorization_results:
            # Primary category
            primary = result.get('primary_category', 'Other')
            stats['category_distribution'][primary] += 1
            
            if primary == 'Other':
                stats['uncategorized_count'] += 1
            
            # Subcategories
            for subcat in result.get('subcategories', []):
                stats['subcategory_distribution'][subcat] += 1
            
            # Confidence scores
            for category, score in result.get('confidence_scores', {}).items():
                confidence_sums[category] += score
                confidence_counts[category] += 1
        
        # Calculate average confidence
        for category, sum_score in confidence_sums.items():
            count = confidence_counts[category]
            stats['average_confidence'][category] = sum_score / count if count > 0 else 0
        
        # Convert defaultdicts to regular dicts for JSON serialization
        stats['category_distribution'] = dict(stats['category_distribution'])
        stats['subcategory_distribution'] = dict(stats['subcategory_distribution'])
        
        return stats
    
    def suggest_new_categories(
        self,
        uncategorized_items: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Suggest new categories based on uncategorized content.
        
        Args:
            uncategorized_items: Items that couldn't be categorized well
            
        Returns:
            List of suggested new categories
        """
        # In a real implementation, this would use clustering or topic modeling
        # For now, return empty list
        return []