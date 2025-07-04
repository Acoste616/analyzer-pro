"""Knowledge base generation module for creating structured learning resources."""

import json
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import defaultdict

from ..analyzers import ContentAnalyzer, Categorizer, Tagger
from ..utils.logger import get_logger, log_execution_time, ProgressLogger
from ..config import get_settings

logger = get_logger(__name__)


class KnowledgeBaseGenerator:
    """Generate structured knowledge base from analyzed content."""
    
    def __init__(
        self,
        content_analyzer: Optional[ContentAnalyzer] = None,
        categorizer: Optional[Categorizer] = None,
        tagger: Optional[Tagger] = None
    ):
        """
        Initialize knowledge base generator.
        
        Args:
            content_analyzer: Content analyzer instance
            categorizer: Categorizer instance
            tagger: Tagger instance
        """
        self.settings = get_settings()
        self.content_analyzer = content_analyzer or ContentAnalyzer()
        self.categorizer = categorizer or Categorizer()
        self.tagger = tagger or Tagger()
        
        # Knowledge base storage
        self.knowledge_base = {
            'items': [],
            'categories': defaultdict(list),
            'tags': defaultdict(list),
            'learning_paths': [],
            'metadata': {
                'version': '1.0',
                'created_at': datetime.now().isoformat(),
                'total_items': 0
            }
        }
    
    @log_execution_time
    async def generate_knowledge_base(
        self,
        extraction_results: Dict[str, Any],
        output_dir: Optional[Path] = None,
        analysis_depth: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        Generate complete knowledge base from extraction results.
        
        Args:
            extraction_results: Results from content extraction
            output_dir: Directory to save knowledge base
            analysis_depth: Depth of content analysis
            
        Returns:
            Generated knowledge base
        """
        logger.info("Starting knowledge base generation")
        
        # Prepare all content items
        all_items = self._prepare_content_items(extraction_results)
        logger.info(f"Processing {len(all_items)} content items")
        
        # Process items in batches
        batch_size = self.settings.processing.batch_size
        processed_items = []
        
        with ProgressLogger(len(all_items), "Generating knowledge base") as progress:
            for i in range(0, len(all_items), batch_size):
                batch = all_items[i:i + batch_size]
                batch_results = await self._process_batch(batch, analysis_depth)
                processed_items.extend(batch_results)
                progress.update(len(batch))
        
        # Build knowledge base structure
        self._build_knowledge_base(processed_items)
        
        # Generate learning paths
        self.knowledge_base['learning_paths'] = self._generate_learning_paths()
        
        # Update metadata
        self.knowledge_base['metadata']['total_items'] = len(processed_items)
        self.knowledge_base['metadata']['updated_at'] = datetime.now().isoformat()
        
        # Save if output directory provided
        if output_dir:
            self._save_knowledge_base(output_dir)
        
        logger.info(f"Knowledge base generated with {len(processed_items)} items")
        return self.knowledge_base
    
    def _prepare_content_items(self, extraction_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Prepare and flatten all content items."""
        items = []
        
        # Add standalone tweets
        for tweet in extraction_results.get('standalone_tweets', []):
            tweet['content_type'] = 'tweet'
            items.append(tweet)
        
        # Add threads
        for thread in extraction_results.get('threads', []):
            thread['content_type'] = 'thread'
            items.append(thread)
        
        # Add videos
        for video in extraction_results.get('videos', []):
            video['content_type'] = 'video'
            items.append(video)
        
        return items
    
    async def _process_batch(
        self,
        batch: List[Dict[str, Any]],
        analysis_depth: str
    ) -> List[Dict[str, Any]]:
        """Process a batch of content items."""
        # Analyze content
        analyses = await self.content_analyzer.batch_analyze(batch, analysis_depth)
        
        # Categorize content
        categorizations = await self.categorizer.batch_categorize(batch)
        
        # Generate tags
        taggings = await self.tagger.batch_generate_tags(batch)
        
        # Combine results
        processed_items = []
        for i, item in enumerate(batch):
            knowledge_item = self._create_knowledge_item(
                item,
                analyses[i],
                categorizations[i],
                taggings[i]
            )
            processed_items.append(knowledge_item)
        
        return processed_items
    
    def _create_knowledge_item(
        self,
        content_item: Dict[str, Any],
        analysis: Dict[str, Any],
        categorization: Dict[str, Any],
        tagging: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a structured knowledge item."""
        # Generate unique ID if not present
        item_id = content_item.get('id', str(uuid.uuid4()))
        
        knowledge_item = {
            'id': item_id,
            'title': content_item.get('title', self._generate_title(content_item)),
            'type': content_item.get('content_type', 'unknown'),
            'content': {
                'original': content_item.get('content', ''),
                'processed': self._process_content(content_item),
                'summary': analysis.get('summary', ''),
                'key_points': self._extract_key_points(analysis),
                'actionable_items': self._extract_actionable_items(analysis)
            },
            'metadata': {
                'source': content_item.get('url', ''),
                'author': content_item.get('author', ''),
                'created_at': content_item.get('created_at', ''),
                'language': analysis.get('quality_metrics', {}).get('language', 'en'),
                'duration': self._calculate_duration(content_item),
                'difficulty': self._determine_difficulty(analysis, tagging)
            },
            'categorization': {
                'primary_category': categorization.get('primary_category', 'Other'),
                'subcategories': categorization.get('subcategories', []),
                'tags': tagging.get('tags', []),
                'confidence_score': max(
                    categorization.get('confidence_scores', {}).values(),
                    default=0.0
                )
            },
            'learning': {
                'learning_objectives': self._extract_learning_objectives(analysis),
                'prerequisites': self._identify_prerequisites(analysis),
                'estimated_time': self._estimate_learning_time(content_item),
                'exercises': self._suggest_exercises(analysis),
                'related_content': []  # Will be populated later
            },
            'quality': {
                'overall_score': analysis.get('quality_metrics', {}).get('content_quality_score', 0),
                'credibility_score': self._calculate_credibility_score(content_item, analysis),
                'usefulness_score': self._calculate_usefulness_score(analysis),
                'freshness_score': self._calculate_freshness_score(content_item)
            }
        }
        
        return knowledge_item
    
    def _generate_title(self, content_item: Dict[str, Any]) -> str:
        """Generate title if not present."""
        content = content_item.get('content', '')
        if len(content) > 100:
            return content[:97] + "..."
        return content or "Untitled"
    
    def _process_content(self, content_item: Dict[str, Any]) -> str:
        """Process content for better readability."""
        content = content_item.get('content', '')
        
        # For threads, already formatted
        if content_item.get('content_type') == 'thread':
            return content
        
        # Clean up content
        # Remove excessive line breaks
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # Remove URLs for cleaner reading (keep them in metadata)
        content = re.sub(r'https?://\S+', '[link]', content)
        
        return content.strip()
    
    def _extract_key_points(self, analysis: Dict[str, Any]) -> List[str]:
        """Extract key points from analysis."""
        # Try to get from analysis
        if 'key_points' in analysis:
            return analysis['key_points']
        
        # Try to parse from raw analysis
        if 'raw_analysis' in analysis:
            # Simple extraction - in production would use NLP
            lines = analysis['raw_analysis'].split('\n')
            key_points = []
            for line in lines:
                if any(marker in line.lower() for marker in ['key point', 'important', 'main']):
                    key_points.append(line.strip())
            return key_points[:5]
        
        return []
    
    def _extract_actionable_items(self, analysis: Dict[str, Any]) -> List[str]:
        """Extract actionable items from analysis."""
        if 'actionable_items' in analysis:
            return analysis['actionable_items']
        
        if 'actionable_takeaways' in analysis:
            return analysis['actionable_takeaways']
        
        return []
    
    def _calculate_duration(self, content_item: Dict[str, Any]) -> str:
        """Calculate content duration."""
        content_type = content_item.get('content_type', '')
        
        if content_type == 'video':
            duration_seconds = content_item.get('duration', 0)
            if duration_seconds > 3600:
                return f"{duration_seconds // 3600}h {(duration_seconds % 3600) // 60}m"
            elif duration_seconds > 60:
                return f"{duration_seconds // 60}m"
            else:
                return f"{duration_seconds}s"
        
        # For text content, estimate reading time
        content = content_item.get('content', '')
        words = len(content.split())
        minutes = max(1, words // 200)
        return f"{minutes}m"
    
    def _determine_difficulty(
        self,
        analysis: Dict[str, Any],
        tagging: Dict[str, Any]
    ) -> str:
        """Determine content difficulty level."""
        # Check tags first
        for tag in tagging.get('tags', []):
            if 'beginner' in tag.lower():
                return 'beginner'
            elif 'advanced' in tag.lower():
                return 'advanced'
            elif 'intermediate' in tag.lower():
                return 'intermediate'
        
        # Check analysis
        if 'difficulty' in analysis:
            return analysis['difficulty']
        
        # Default based on content length and complexity
        # This is simplified - in production would use more sophisticated analysis
        return 'intermediate'
    
    def _extract_learning_objectives(self, analysis: Dict[str, Any]) -> List[str]:
        """Extract learning objectives."""
        if 'learning_objectives' in analysis:
            return analysis['learning_objectives']
        
        # Generate basic objectives based on content type
        objectives = []
        if 'key_points' in analysis:
            for point in analysis['key_points'][:3]:
                objectives.append(f"Understand {point}")
        
        return objectives
    
    def _identify_prerequisites(self, analysis: Dict[str, Any]) -> List[str]:
        """Identify prerequisites for content."""
        if 'prerequisites' in analysis:
            return analysis['prerequisites']
        
        # Basic prerequisite identification
        prerequisites = []
        
        # Check for technical terms that imply prerequisites
        content = str(analysis.get('raw_analysis', ''))
        
        tech_prerequisites = {
            'advanced': ['Basic understanding of the topic'],
            'api': ['Basic programming knowledge'],
            'machine learning': ['Python basics', 'Statistics fundamentals'],
            'react': ['JavaScript knowledge', 'HTML/CSS basics'],
            'docker': ['Command line basics', 'Basic DevOps concepts']
        }
        
        for term, prereqs in tech_prerequisites.items():
            if term in content.lower():
                prerequisites.extend(prereqs)
        
        return list(set(prerequisites))[:3]
    
    def _estimate_learning_time(self, content_item: Dict[str, Any]) -> str:
        """Estimate time to learn/complete content."""
        duration = self._calculate_duration(content_item)
        
        # Add time for exercises and practice
        content_type = content_item.get('content_type', '')
        if content_type == 'video':
            # Videos usually need 1.5x time for notes and practice
            return duration
        elif content_type == 'thread':
            # Threads are usually quick reads
            return duration
        else:
            # Articles might need re-reading
            return duration
    
    def _suggest_exercises(self, analysis: Dict[str, Any]) -> List[str]:
        """Suggest practical exercises."""
        exercises = []
        
        # Check if analysis contains exercises
        if 'exercises' in analysis:
            return analysis['exercises']
        
        # Generate basic exercises based on content
        if 'key_points' in analysis:
            for i, point in enumerate(analysis['key_points'][:2]):
                exercises.append(f"Practice exercise {i+1}: Apply {point}")
        
        return exercises
    
    def _calculate_credibility_score(
        self,
        content_item: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> float:
        """Calculate source credibility score."""
        score = 0.5  # Base score
        
        # Author reputation (simplified)
        author = content_item.get('author', '')
        if author:
            score += 0.2
        
        # Source quality
        if 'quality_metrics' in analysis:
            quality = analysis['quality_metrics'].get('content_quality_score', 0)
            score += quality * 0.3
        
        return min(1.0, score)
    
    def _calculate_usefulness_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate content usefulness score."""
        score = 0.0
        
        # Has actionable items
        if analysis.get('actionable_items'):
            score += 0.3
        
        # Has key points
        if analysis.get('key_points'):
            score += 0.3
        
        # Quality score
        quality = analysis.get('quality_metrics', {}).get('content_quality_score', 0)
        score += quality * 0.4
        
        return min(1.0, score)
    
    def _calculate_freshness_score(self, content_item: Dict[str, Any]) -> float:
        """Calculate content freshness score."""
        created_at = content_item.get('created_at')
        if not created_at:
            return 0.5
        
        try:
            # Parse date
            if isinstance(created_at, str):
                created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            else:
                created_date = created_at
            
            # Calculate age in days
            age_days = (datetime.now() - created_date).days
            
            # Score based on age
            if age_days < 7:
                return 1.0
            elif age_days < 30:
                return 0.8
            elif age_days < 90:
                return 0.6
            elif age_days < 365:
                return 0.4
            else:
                return 0.2
        except:
            return 0.5
    
    def _build_knowledge_base(self, processed_items: List[Dict[str, Any]]):
        """Build the knowledge base structure."""
        self.knowledge_base['items'] = processed_items
        
        # Organize by category
        for item in processed_items:
            primary_category = item['categorization']['primary_category']
            self.knowledge_base['categories'][primary_category].append(item['id'])
            
            # Organize by tags
            for tag in item['categorization']['tags']:
                self.knowledge_base['tags'][tag].append(item['id'])
        
        # Find related content
        self._find_related_content()
    
    def _find_related_content(self):
        """Find and link related content items."""
        # Simple implementation - find items with similar tags
        for i, item in enumerate(self.knowledge_base['items']):
            item_tags = set(item['categorization']['tags'])
            related = []
            
            for j, other_item in enumerate(self.knowledge_base['items']):
                if i != j:
                    other_tags = set(other_item['categorization']['tags'])
                    
                    # Calculate similarity
                    common_tags = item_tags.intersection(other_tags)
                    if len(common_tags) >= 2:
                        related.append({
                            'id': other_item['id'],
                            'similarity': len(common_tags) / len(item_tags.union(other_tags))
                        })
            
            # Sort by similarity and keep top 5
            related.sort(key=lambda x: x['similarity'], reverse=True)
            item['learning']['related_content'] = [r['id'] for r in related[:5]]
    
    def _generate_learning_paths(self) -> List[Dict[str, Any]]:
        """Generate suggested learning paths."""
        learning_paths = []
        
        # Group items by category and difficulty
        category_items = defaultdict(lambda: defaultdict(list))
        
        for item in self.knowledge_base['items']:
            category = item['categorization']['primary_category']
            difficulty = item['metadata']['difficulty']
            category_items[category][difficulty].append(item)
        
        # Create learning paths for each category
        for category, difficulty_items in category_items.items():
            if len(difficulty_items) >= 2:  # Need at least 2 difficulty levels
                path = {
                    'id': str(uuid.uuid4()),
                    'title': f"{category} Learning Path",
                    'category': category,
                    'description': f"Progressive learning path for {category}",
                    'items': []
                }
                
                # Add items in difficulty order
                for difficulty in ['beginner', 'intermediate', 'advanced']:
                    if difficulty in difficulty_items:
                        for item in difficulty_items[difficulty][:3]:  # Max 3 per level
                            path['items'].append({
                                'id': item['id'],
                                'title': item['title'],
                                'difficulty': difficulty,
                                'estimated_time': item['learning']['estimated_time']
                            })
                
                if path['items']:
                    learning_paths.append(path)
        
        return learning_paths
    
    def _save_knowledge_base(self, output_dir: Path):
        """Save knowledge base to disk."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save main knowledge base
        kb_file = output_dir / 'knowledge_base.json'
        with open(kb_file, 'w', encoding='utf-8') as f:
            json.dump(self.knowledge_base, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Knowledge base saved to {kb_file}")
        
        # Save category index
        category_file = output_dir / 'categories.json'
        with open(category_file, 'w', encoding='utf-8') as f:
            json.dump(dict(self.knowledge_base['categories']), f, indent=2)
        
        # Save tag index
        tag_file = output_dir / 'tags.json'
        with open(tag_file, 'w', encoding='utf-8') as f:
            json.dump(dict(self.knowledge_base['tags']), f, indent=2)
        
        # Save learning paths
        paths_file = output_dir / 'learning_paths.json'
        with open(paths_file, 'w', encoding='utf-8') as f:
            json.dump(self.knowledge_base['learning_paths'], f, indent=2)
    
    def export_for_anki(self, output_file: Path):
        """Export knowledge base as Anki deck."""
        # This would generate Anki-compatible format
        # For now, create a simple CSV
        import csv
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Question', 'Answer', 'Tags'])
            
            for item in self.knowledge_base['items']:
                # Create flashcards from key points
                for point in item['content']['key_points']:
                    question = f"What is important about: {item['title']}"
                    answer = point
                    tags = ' '.join(item['categorization']['tags'])
                    writer.writerow([question, answer, tags])
    
    def export_for_notion(self, output_file: Path):
        """Export knowledge base for Notion import."""
        # Create Notion-compatible CSV
        import csv
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Title', 'Type', 'Category', 'Tags', 'Summary',
                'URL', 'Author', 'Difficulty', 'Duration', 'Quality Score'
            ])
            
            for item in self.knowledge_base['items']:
                writer.writerow([
                    item['title'],
                    item['type'],
                    item['categorization']['primary_category'],
                    ', '.join(item['categorization']['tags']),
                    item['content']['summary'],
                    item['metadata']['source'],
                    item['metadata']['author'],
                    item['metadata']['difficulty'],
                    item['metadata']['duration'],
                    item['quality']['overall_score']
                ])
    
    def export_for_obsidian(self, output_dir: Path):
        """Export knowledge base as Obsidian vault."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for item in self.knowledge_base['items']:
            # Create markdown file for each item
            filename = self._sanitize_filename(item['title']) + '.md'
            file_path = output_dir / filename
            
            with open(file_path, 'w', encoding='utf-8') as f:
                # Front matter
                f.write('---\n')
                f.write(f"title: {item['title']}\n")
                f.write(f"type: {item['type']}\n")
                f.write(f"category: {item['categorization']['primary_category']}\n")
                f.write(f"tags: {', '.join(item['categorization']['tags'])}\n")
                f.write(f"difficulty: {item['metadata']['difficulty']}\n")
                f.write(f"created: {item['metadata']['created_at']}\n")
                f.write('---\n\n')
                
                # Content
                f.write(f"# {item['title']}\n\n")
                
                # Metadata
                f.write(f"**Author:** {item['metadata']['author']}\n")
                f.write(f"**Source:** {item['metadata']['source']}\n")
                f.write(f"**Duration:** {item['metadata']['duration']}\n\n")
                
                # Summary
                if item['content']['summary']:
                    f.write("## Summary\n\n")
                    f.write(f"{item['content']['summary']}\n\n")
                
                # Key Points
                if item['content']['key_points']:
                    f.write("## Key Points\n\n")
                    for point in item['content']['key_points']:
                        f.write(f"- {point}\n")
                    f.write("\n")
                
                # Content
                f.write("## Content\n\n")
                f.write(item['content']['processed'])
                f.write("\n\n")
                
                # Related Content
                if item['learning']['related_content']:
                    f.write("## Related Content\n\n")
                    for related_id in item['learning']['related_content']:
                        # Find related item
                        related_item = next(
                            (i for i in self.knowledge_base['items'] if i['id'] == related_id),
                            None
                        )
                        if related_item:
                            related_filename = self._sanitize_filename(related_item['title'])
                            f.write(f"- [[{related_filename}]]\n")
    
    def _sanitize_filename(self, title: str) -> str:
        """Sanitize title for use as filename."""
        # Remove invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            title = title.replace(char, '')
        
        # Limit length
        if len(title) > 100:
            title = title[:100]
        
        return title.strip() or 'untitled'