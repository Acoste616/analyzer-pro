"""Main bookmark processor orchestration module."""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from .content_extractor import ContentExtractor
from .knowledge_base_generator import KnowledgeBaseGenerator
from ..utils.logger import get_logger, log_execution_time
from ..utils.checkpoint_manager import CheckpointManager
from ..config import get_settings

logger = get_logger(__name__)


class BookmarkProcessor:
    """Main orchestrator for bookmark processing pipeline."""
    
    def __init__(
        self,
        config_path: Optional[Path] = None,
        checkpoint_dir: Optional[Path] = None
    ):
        """
        Initialize bookmark processor.
        
        Args:
            config_path: Path to configuration file
            checkpoint_dir: Directory for checkpoints
        """
        self.settings = get_settings(config_path)
        
        # Initialize checkpoint manager
        checkpoint_path = checkpoint_dir or Path(self.settings.processing.checkpoint_dir)
        self.checkpoint_manager = CheckpointManager(checkpoint_path)
        
        # Initialize components
        self.content_extractor = ContentExtractor(
            checkpoint_manager=self.checkpoint_manager,
            enable_video_extraction=self.settings.processing.enable_video_extraction,
            enable_thread_reconstruction=self.settings.processing.enable_thread_reconstruction
        )
        
        self.knowledge_generator = KnowledgeBaseGenerator()
        
        # Processing state
        self.processing_stats = {
            'start_time': None,
            'end_time': None,
            'total_items': 0,
            'processed_items': 0,
            'errors': [],
            'warnings': []
        }
    
    @log_execution_time
    async def process_bookmarks(
        self,
        input_path: Path,
        output_dir: Path,
        resume: bool = True,
        export_formats: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Process bookmarks through the complete pipeline.
        
        Args:
            input_path: Path to input file (CSV or JSON)
            output_dir: Directory for output files
            resume: Whether to resume from checkpoint
            export_formats: Export formats (json, anki, notion, obsidian)
            
        Returns:
            Processing results and statistics
        """
        logger.info(f"Starting bookmark processing pipeline")
        logger.info(f"Input: {input_path}")
        logger.info(f"Output: {output_dir}")
        
        self.processing_stats['start_time'] = datetime.now()
        
        try:
            # Step 1: Extract content
            logger.info("Step 1: Extracting content from bookmarks")
            extraction_results = await self.content_extractor.extract_all_content(
                input_path,
                resume_from_checkpoint=resume
            )
            
            self.processing_stats['total_items'] = extraction_results['statistics']['total_items']
            logger.info(f"Extracted {self.processing_stats['total_items']} items")
            
            # Step 2: Generate knowledge base
            logger.info("Step 2: Generating knowledge base")
            knowledge_base = await self.knowledge_generator.generate_knowledge_base(
                extraction_results,
                output_dir=output_dir,
                analysis_depth=self.settings.processing.analysis_depth
            )
            
            self.processing_stats['processed_items'] = knowledge_base['metadata']['total_items']
            
            # Step 3: Export in requested formats
            if export_formats:
                logger.info(f"Step 3: Exporting in formats: {export_formats}")
                await self._export_results(knowledge_base, output_dir, export_formats)
            
            # Generate final report
            self.processing_stats['end_time'] = datetime.now()
            report = self._generate_processing_report(extraction_results, knowledge_base)
            
            # Save report
            report_path = output_dir / 'processing_report.json'
            self._save_report(report, report_path)
            
            logger.info("Bookmark processing completed successfully")
            return report
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            self.processing_stats['errors'].append(str(e))
            raise
    
    async def _export_results(
        self,
        knowledge_base: Dict[str, Any],
        output_dir: Path,
        export_formats: List[str]
    ):
        """Export results in various formats."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for format_name in export_formats:
            try:
                if format_name == 'json':
                    # Already saved by knowledge generator
                    logger.info("JSON format already exported")
                    
                elif format_name == 'anki':
                    logger.info("Exporting Anki deck")
                    anki_file = output_dir / 'bookmarks_anki.csv'
                    self.knowledge_generator.export_for_anki(anki_file)
                    
                elif format_name == 'notion':
                    logger.info("Exporting for Notion")
                    notion_file = output_dir / 'bookmarks_notion.csv'
                    self.knowledge_generator.export_for_notion(notion_file)
                    
                elif format_name == 'obsidian':
                    logger.info("Exporting Obsidian vault")
                    obsidian_dir = output_dir / 'obsidian_vault'
                    self.knowledge_generator.export_for_obsidian(obsidian_dir)
                    
                else:
                    logger.warning(f"Unknown export format: {format_name}")
                    self.processing_stats['warnings'].append(f"Unknown export format: {format_name}")
                    
            except Exception as e:
                logger.error(f"Failed to export {format_name}: {e}")
                self.processing_stats['errors'].append(f"Export {format_name}: {str(e)}")
    
    def _generate_processing_report(
        self,
        extraction_results: Dict[str, Any],
        knowledge_base: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate comprehensive processing report."""
        duration = (self.processing_stats['end_time'] - self.processing_stats['start_time']).total_seconds()
        
        report = {
            'summary': {
                'status': 'completed' if not self.processing_stats['errors'] else 'completed_with_errors',
                'start_time': self.processing_stats['start_time'].isoformat(),
                'end_time': self.processing_stats['end_time'].isoformat(),
                'duration_seconds': duration,
                'duration_formatted': self._format_duration(duration),
                'total_items_processed': self.processing_stats['processed_items'],
                'errors_count': len(self.processing_stats['errors']),
                'warnings_count': len(self.processing_stats['warnings'])
            },
            'extraction': extraction_results['statistics'],
            'knowledge_base': {
                'total_items': knowledge_base['metadata']['total_items'],
                'categories': self._get_category_summary(knowledge_base),
                'tags': self._get_tag_summary(knowledge_base),
                'learning_paths': len(knowledge_base['learning_paths']),
                'quality_distribution': self._get_quality_distribution(knowledge_base)
            },
            'errors': self.processing_stats['errors'],
            'warnings': self.processing_stats['warnings'],
            'configuration': {
                'analysis_depth': self.settings.processing.analysis_depth,
                'batch_size': self.settings.processing.batch_size,
                'llm_providers': self._get_active_llm_providers(),
                'video_extraction_enabled': self.settings.processing.enable_video_extraction,
                'thread_reconstruction_enabled': self.settings.processing.enable_thread_reconstruction
            }
        }
        
        return report
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        
        return " ".join(parts)
    
    def _get_category_summary(self, knowledge_base: Dict[str, Any]) -> Dict[str, int]:
        """Get category distribution summary."""
        summary = {}
        for category, items in knowledge_base['categories'].items():
            summary[category] = len(items)
        return dict(sorted(summary.items(), key=lambda x: x[1], reverse=True))
    
    def _get_tag_summary(self, knowledge_base: Dict[str, Any]) -> Dict[str, Any]:
        """Get tag statistics summary."""
        all_tags = []
        for item in knowledge_base['items']:
            all_tags.extend(item['categorization']['tags'])
        
        from collections import Counter
        tag_counts = Counter(all_tags)
        
        return {
            'total_unique_tags': len(set(all_tags)),
            'total_tag_occurrences': len(all_tags),
            'top_tags': dict(tag_counts.most_common(20))
        }
    
    def _get_quality_distribution(self, knowledge_base: Dict[str, Any]) -> Dict[str, int]:
        """Get quality score distribution."""
        distribution = {
            'high': 0,     # > 0.7
            'medium': 0,   # 0.4 - 0.7
            'low': 0       # < 0.4
        }
        
        for item in knowledge_base['items']:
            score = item['quality']['overall_score']
            if score > 0.7:
                distribution['high'] += 1
            elif score > 0.4:
                distribution['medium'] += 1
            else:
                distribution['low'] += 1
        
        return distribution
    
    def _get_active_llm_providers(self) -> List[str]:
        """Get list of configured LLM providers."""
        providers = []
        
        if self.settings.claude and self.settings.claude.api_key:
            providers.append('claude')
        if self.settings.gemini and self.settings.gemini.api_key:
            providers.append('gemini')
        if self.settings.grok and self.settings.grok.api_key:
            providers.append('grok')
        
        return providers
    
    def _save_report(self, report: Dict[str, Any], report_path: Path):
        """Save processing report."""
        import json
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Processing report saved to {report_path}")
    
    async def process_single_bookmark(
        self,
        bookmark_data: Dict[str, Any],
        analyze: bool = True
    ) -> Dict[str, Any]:
        """
        Process a single bookmark item.
        
        Args:
            bookmark_data: Bookmark data dictionary
            analyze: Whether to perform analysis
            
        Returns:
            Processed bookmark data
        """
        # Extract content based on type
        content_type = self.content_extractor._identify_content_type(bookmark_data)
        
        if content_type == 'video' and self.content_extractor.video_extractor:
            async with self.content_extractor.video_extractor as extractor:
                extracted = await extractor.extract_video_info(bookmark_data['url'])
        else:
            # Process as tweet/text
            extracted = await self.content_extractor.tweet_extractor._enrich_tweet_data(bookmark_data)
        
        if not analyze or not extracted:
            return extracted
        
        # Analyze content
        analysis = await self.knowledge_generator.content_analyzer.analyze_content(extracted)
        categorization = await self.knowledge_generator.categorizer.categorize_content(extracted)
        tagging = await self.knowledge_generator.tagger.generate_tags(extracted)
        
        # Create knowledge item
        knowledge_item = self.knowledge_generator._create_knowledge_item(
            extracted,
            analysis,
            categorization,
            tagging
        )
        
        return knowledge_item
    
    def get_checkpoint_status(self) -> Optional[Dict[str, Any]]:
        """Get current checkpoint status."""
        checkpoint = self.checkpoint_manager.get_latest_checkpoint()
        
        if not checkpoint:
            return None
        
        return {
            'checkpoint_id': checkpoint.checkpoint_id,
            'created_at': checkpoint.created_at.isoformat(),
            'updated_at': checkpoint.updated_at.isoformat(),
            'status': checkpoint.status,
            'progress': checkpoint.progress,
            'is_complete': checkpoint.is_complete,
            'can_resume': not checkpoint.is_complete and checkpoint.status != 'failed'
        }
    
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List all available checkpoints."""
        checkpoints = self.checkpoint_manager.list_checkpoints()
        
        return [
            {
                'checkpoint_id': cp.checkpoint_id,
                'created_at': cp.created_at.isoformat(),
                'status': cp.status,
                'progress': cp.progress,
                'is_complete': cp.is_complete
            }
            for cp in checkpoints
        ]
    
    async def validate_configuration(self) -> Dict[str, Any]:
        """Validate current configuration."""
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'llm_status': {}
        }
        
        # Check LLM configurations
        for provider in ['claude', 'gemini', 'grok']:
            config = getattr(self.settings, provider, None)
            if config and config.api_key:
                # Test connection
                try:
                    if provider == 'claude':
                        from ..llm import ClaudeClient
                        client = ClaudeClient(config.dict())
                        # Simple test
                        await client.complete("Test")
                        validation_results['llm_status'][provider] = 'active'
                    # Similar for other providers
                except Exception as e:
                    validation_results['llm_status'][provider] = f'error: {str(e)}'
                    validation_results['warnings'].append(f"{provider} connection failed: {e}")
            else:
                validation_results['llm_status'][provider] = 'not_configured'
        
        # Check paths
        checkpoint_dir = Path(self.settings.processing.checkpoint_dir)
        if not checkpoint_dir.exists():
            try:
                checkpoint_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                validation_results['errors'].append(f"Cannot create checkpoint directory: {e}")
                validation_results['valid'] = False
        
        # Check if at least one LLM is configured
        if not any(status == 'active' for status in validation_results['llm_status'].values()):
            validation_results['errors'].append("No LLM provider is properly configured")
            validation_results['valid'] = False
        
        return validation_results