import asyncio
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..config.settings import settings_manager
from ..utils.logger import get_logger
from ..llm.grok_client import GrokClient
from ..llm.claude_client import ClaudeClient
from ..llm.gemini_client import GeminiClient


@dataclass
class CategoryResult:
    primary_category: str
    secondary_categories: List[str]
    confidence_scores: Dict[str, float]
    category_hierarchy: Dict[str, Any]
    categorization_metadata: Dict[str, Any]


class Categorizer:
    def __init__(self):
        self.settings = settings_manager.settings
        self.logger = get_logger(__name__)
        self.llm_configs = settings_manager.llm_configs
        
        # Define category hierarchy
        self.category_hierarchy = {
            "Technology": {
                "Programming": ["Python", "JavaScript", "Java", "C++", "Go", "Rust"],
                "Web Development": ["Frontend", "Backend", "Full Stack", "APIs", "Frameworks"],
                "Data Science": ["Machine Learning", "AI", "Analytics", "Big Data", "Statistics"],
                "DevOps": ["Docker", "Kubernetes", "CI/CD", "Cloud", "Infrastructure"],
                "Mobile": ["iOS", "Android", "React Native", "Flutter", "Cross Platform"],
                "Security": ["Cybersecurity", "Penetration Testing", "Cryptography", "Privacy"]
            },
            "Business": {
                "Startups": ["Entrepreneurship", "Funding", "Business Model", "Growth"],
                "Marketing": ["Digital Marketing", "Content Marketing", "SEO", "Social Media"],
                "Management": ["Leadership", "Team Building", "Strategy", "Operations"],
                "Finance": ["Investment", "Accounting", "Financial Planning", "Economics"],
                "Sales": ["Lead Generation", "CRM", "Sales Strategy", "Customer Success"]
            },
            "Education": {
                "Online Learning": ["Courses", "Tutorials", "Certifications", "MOOCs"],
                "Academic": ["Research", "Papers", "Studies", "Universities"],
                "Skills Development": ["Career Growth", "Professional Development", "Training"],
                "Teaching": ["Pedagogy", "Educational Technology", "Curriculum"]
            },
            "Science": {
                "Research": ["Academic Research", "Scientific Studies", "Publications"],
                "Mathematics": ["Statistics", "Algorithms", "Mathematical Modeling"],
                "Physics": ["Quantum Physics", "Theoretical Physics", "Applied Physics"],
                "Biology": ["Biotechnology", "Genetics", "Medical Research"]
            },
            "Lifestyle": {
                "Health": ["Fitness", "Nutrition", "Mental Health", "Wellness"],
                "Travel": ["Destinations", "Travel Tips", "Culture", "Adventure"],
                "Hobbies": ["Photography", "Gaming", "Reading", "Sports"],
                "Personal Development": ["Self Improvement", "Productivity", "Mindfulness"]
            }
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
    
    async def categorize(self, content: str, preferred_provider: str = None) -> List[str]:
        """
        Categorize content using LLM
        
        Args:
            content: Text content to categorize
            preferred_provider: Preferred LLM provider
            
        Returns:
            List of categories
        """
        category_result = await self.categorize_detailed(content, preferred_provider)
        
        # Return combined categories
        categories = [category_result.primary_category]
        categories.extend(category_result.secondary_categories)
        
        return categories
    
    async def categorize_detailed(self, content: str, preferred_provider: str = None) -> CategoryResult:
        """
        Categorize content with detailed results
        
        Args:
            content: Text content to categorize
            preferred_provider: Preferred LLM provider
            
        Returns:
            CategoryResult object with detailed categorization
        """
        if not content or not content.strip():
            raise ValueError("Content cannot be empty")
        
        # Choose provider
        provider = preferred_provider or self.settings.analysis.default_llm_provider
        if provider not in self.clients:
            provider = next(iter(self.clients.keys()))
        
        client = self.clients[provider]
        
        # Get categorization prompts
        categorization_prompts = settings_manager.get_analysis_prompt("categorization")
        if not categorization_prompts:
            raise ValueError("Categorization prompts not found in configuration")
        
        # Prepare prompt with available categories
        available_categories = self._get_available_categories()
        enhanced_system_prompt = categorization_prompts["system_prompt"] + f"\n\nAvailable categories: {', '.join(available_categories)}"
        
        user_prompt = categorization_prompts["user_prompt"].format(content=content)
        
        try:
            async with client:
                # Generate categorization response
                response = await client.generate(
                    prompt=user_prompt,
                    system_prompt=enhanced_system_prompt,
                    temperature=0.2,  # Lower temperature for more consistent categorization
                    max_tokens=500
                )
                
                # Parse the response
                category_result = self._parse_categorization_response(response.content, content)
                
                # Add metadata
                category_result.categorization_metadata = {
                    "provider": provider,
                    "model": response.model,
                    "processing_time": response.processing_time,
                    "categorized_at": datetime.now().isoformat(),
                    "prompt_tokens": response.usage.get("prompt_tokens", 0),
                    "completion_tokens": response.usage.get("completion_tokens", 0),
                    "total_tokens": response.usage.get("total_tokens", 0)
                }
                
                return category_result
                
        except Exception as e:
            self.logger.error(f"Error categorizing content with {provider}: {str(e)}")
            # Return fallback categorization
            return self._fallback_categorization(content)
    
    def _get_available_categories(self) -> List[str]:
        """Get list of all available categories"""
        categories = []
        for main_category, subcategories in self.category_hierarchy.items():
            categories.append(main_category)
            for subcategory, specific_categories in subcategories.items():
                categories.append(subcategory)
                categories.extend(specific_categories)
        return categories
    
    def _parse_categorization_response(self, response_content: str, original_content: str) -> CategoryResult:
        """Parse LLM response into structured categorization result"""
        
        # Initialize default values
        primary_category = "Other"
        secondary_categories = []
        confidence_scores = {}
        
        try:
            # Try to parse structured response
            lines = response_content.strip().split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Identify sections
                if line.startswith('**Primary Category**') or line.startswith('- **Primary Category**'):
                    current_section = 'primary'
                elif line.startswith('**Secondary Categories**') or line.startswith('- **Secondary Categories**'):
                    current_section = 'secondary'
                elif line.startswith('**Confidence Score**') or line.startswith('- **Confidence Score**'):
                    current_section = 'confidence'
                elif ':' in line and current_section:
                    # Extract value after colon
                    value = line.split(':', 1)[1].strip()
                    if current_section == 'primary':
                        primary_category = value
                    elif current_section == 'confidence':
                        try:
                            confidence_scores[primary_category] = float(value.split('/')[0])
                        except:
                            confidence_scores[primary_category] = 5.0
                elif line.startswith('- ') and current_section == 'secondary':
                    # Extract secondary category
                    category = line[2:].strip()
                    secondary_categories.append(category)
            
            # Validate categories against hierarchy
            primary_category = self._validate_category(primary_category)
            secondary_categories = [self._validate_category(cat) for cat in secondary_categories]
            secondary_categories = [cat for cat in secondary_categories if cat != primary_category]
            
            # If no valid categories found, use fallback
            if primary_category == "Other" and not secondary_categories:
                return self._fallback_categorization(original_content)
            
        except Exception as e:
            self.logger.warning(f"Error parsing categorization response: {str(e)}")
            return self._fallback_categorization(original_content)
        
        # Build category hierarchy for this result
        category_hierarchy = self._build_category_hierarchy(primary_category, secondary_categories)
        
        return CategoryResult(
            primary_category=primary_category,
            secondary_categories=secondary_categories[:5],  # Limit to top 5
            confidence_scores=confidence_scores,
            category_hierarchy=category_hierarchy,
            categorization_metadata={}
        )
    
    def _validate_category(self, category: str) -> str:
        """Validate category against available categories"""
        if not category:
            return "Other"
        
        # Check if category exists in hierarchy
        available_categories = self._get_available_categories()
        
        # Exact match
        if category in available_categories:
            return category
        
        # Case-insensitive match
        for available_cat in available_categories:
            if category.lower() == available_cat.lower():
                return available_cat
        
        # Partial match
        for available_cat in available_categories:
            if category.lower() in available_cat.lower() or available_cat.lower() in category.lower():
                return available_cat
        
        return "Other"
    
    def _build_category_hierarchy(self, primary: str, secondary: List[str]) -> Dict[str, Any]:
        """Build category hierarchy for the result"""
        hierarchy = {}
        
        # Find primary category in hierarchy
        for main_cat, subcats in self.category_hierarchy.items():
            if primary == main_cat:
                hierarchy[main_cat] = {
                    "type": "main",
                    "subcategories": list(subcats.keys())
                }
                break
            else:
                for subcat, specific_cats in subcats.items():
                    if primary == subcat or primary in specific_cats:
                        hierarchy[main_cat] = {
                            "type": "parent",
                            "subcategory": subcat if primary == subcat else primary,
                            "subcategories": specific_cats
                        }
                        break
        
        # Add secondary categories
        for secondary_cat in secondary:
            for main_cat, subcats in self.category_hierarchy.items():
                if secondary_cat == main_cat:
                    hierarchy[f"{main_cat}_secondary"] = {
                        "type": "secondary_main",
                        "subcategories": list(subcats.keys())
                    }
                    break
                else:
                    for subcat, specific_cats in subcats.items():
                        if secondary_cat == subcat or secondary_cat in specific_cats:
                            hierarchy[f"{main_cat}_secondary"] = {
                                "type": "secondary_parent",
                                "subcategory": subcat if secondary_cat == subcat else secondary_cat,
                                "subcategories": specific_cats
                            }
                            break
        
        return hierarchy
    
    def _fallback_categorization(self, content: str) -> CategoryResult:
        """Fallback categorization using keyword matching"""
        
        content_lower = content.lower()
        category_scores = {}
        
        # Score categories based on keyword presence
        for main_category, subcategories in self.category_hierarchy.items():
            score = 0
            
            # Check main category keywords
            if main_category.lower() in content_lower:
                score += 5
            
            # Check subcategory keywords
            for subcategory, specific_categories in subcategories.items():
                if subcategory.lower() in content_lower:
                    score += 3
                
                # Check specific category keywords
                for specific_category in specific_categories:
                    if specific_category.lower() in content_lower:
                        score += 2
            
            if score > 0:
                category_scores[main_category] = score
        
        # Determine primary and secondary categories
        if category_scores:
            sorted_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
            primary_category = sorted_categories[0][0]
            secondary_categories = [cat for cat, score in sorted_categories[1:4]]  # Top 3 secondary
        else:
            primary_category = "Other"
            secondary_categories = []
        
        # Build confidence scores
        confidence_scores = {}
        for category, score in category_scores.items():
            confidence_scores[category] = min(10.0, score)
        
        return CategoryResult(
            primary_category=primary_category,
            secondary_categories=secondary_categories,
            confidence_scores=confidence_scores,
            category_hierarchy=self._build_category_hierarchy(primary_category, secondary_categories),
            categorization_metadata={"method": "fallback_keyword_matching"}
        )
    
    async def categorize_batch(self, 
                             contents: List[str],
                             preferred_provider: str = None) -> List[CategoryResult]:
        """Categorize multiple contents in batch"""
        
        # Process with concurrency control
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent categorizations
        
        async def categorize_with_semaphore(content):
            async with semaphore:
                return await self.categorize_detailed(content, preferred_provider)
        
        tasks = [categorize_with_semaphore(content) for content in contents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error in batch categorization: {str(result)}")
                # Add a default result for failed categorizations
                valid_results.append(CategoryResult(
                    primary_category="Other",
                    secondary_categories=[],
                    confidence_scores={},
                    category_hierarchy={},
                    categorization_metadata={"error": str(result)}
                ))
            else:
                valid_results.append(result)
        
        return valid_results
    
    def get_category_statistics(self, results: List[CategoryResult]) -> Dict[str, Any]:
        """Get statistics from categorization results"""
        
        if not results:
            return {}
        
        # Count primary categories
        primary_counts = {}
        for result in results:
            category = result.primary_category
            primary_counts[category] = primary_counts.get(category, 0) + 1
        
        # Count all categories (primary + secondary)
        all_counts = {}
        for result in results:
            all_categories = [result.primary_category] + result.secondary_categories
            for category in all_categories:
                all_counts[category] = all_counts.get(category, 0) + 1
        
        # Calculate average confidence
        all_confidence_scores = []
        for result in results:
            all_confidence_scores.extend(result.confidence_scores.values())
        
        avg_confidence = sum(all_confidence_scores) / len(all_confidence_scores) if all_confidence_scores else 0
        
        return {
            "total_categorized": len(results),
            "primary_category_distribution": dict(sorted(primary_counts.items(), key=lambda x: x[1], reverse=True)),
            "all_category_distribution": dict(sorted(all_counts.items(), key=lambda x: x[1], reverse=True)),
            "average_confidence": round(avg_confidence, 2),
            "unique_categories": len(all_counts),
            "categorization_timestamp": datetime.now().isoformat()
        }
    
    def get_category_hierarchy(self) -> Dict[str, Any]:
        """Get the complete category hierarchy"""
        return self.category_hierarchy.copy()
    
    def suggest_new_categories(self, contents: List[str]) -> List[str]:
        """Suggest new categories based on content analysis"""
        
        # Extract frequently occurring terms that might be new categories
        word_counts = {}
        for content in contents:
            words = content.lower().split()
            for word in words:
                if len(word) > 3 and word.isalpha():
                    word_counts[word] = word_counts.get(word, 0) + 1
        
        # Get existing categories
        existing_categories = set(cat.lower() for cat in self._get_available_categories())
        
        # Find potential new categories
        potential_categories = []
        for word, count in word_counts.items():
            if count >= 3 and word not in existing_categories:  # Appears at least 3 times
                potential_categories.append(word.title())
        
        # Sort by frequency and return top suggestions
        return sorted(potential_categories, key=lambda x: word_counts[x.lower()], reverse=True)[:10]