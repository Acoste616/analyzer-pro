import json
import csv
import os
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
import logging

from ..config.settings import settings_manager
from ..utils.logger import get_logger
from .bookmark_processor import ProcessedBookmark


class KnowledgeBaseGenerator:
    def __init__(self):
        self.settings = settings_manager.settings
        self.logger = get_logger(__name__)
        self.output_dir = Path(self.settings.knowledge_base.output_dir)
        self.formats = self.settings.knowledge_base.formats
        self.include_metadata = self.settings.knowledge_base.include_metadata
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def generate_knowledge_base(self, 
                                    processed_bookmarks: List[ProcessedBookmark],
                                    output_name: str = "knowledge_base") -> Dict[str, str]:
        """
        Generate knowledge base in multiple formats
        
        Args:
            processed_bookmarks: List of processed bookmarks
            output_name: Base name for output files
            
        Returns:
            Dictionary mapping format to file path
        """
        self.logger.info(f"Generating knowledge base with {len(processed_bookmarks)} bookmarks")
        
        generated_files = {}
        
        for format_type in self.formats:
            try:
                file_path = await self._generate_format(processed_bookmarks, output_name, format_type)
                generated_files[format_type] = file_path
                self.logger.info(f"Generated {format_type} knowledge base: {file_path}")
            except Exception as e:
                self.logger.error(f"Error generating {format_type} knowledge base: {str(e)}")
        
        # Generate summary statistics
        stats_file = await self._generate_statistics(processed_bookmarks, output_name)
        generated_files['statistics'] = stats_file
        
        return generated_files
    
    async def _generate_format(self, 
                             processed_bookmarks: List[ProcessedBookmark],
                             output_name: str,
                             format_type: str) -> str:
        """Generate knowledge base in specific format"""
        
        if format_type == "json":
            return await self._generate_json(processed_bookmarks, output_name)
        elif format_type == "markdown":
            return await self._generate_markdown(processed_bookmarks, output_name)
        elif format_type == "csv":
            return await self._generate_csv(processed_bookmarks, output_name)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    async def _generate_json(self, 
                           processed_bookmarks: List[ProcessedBookmark],
                           output_name: str) -> str:
        """Generate JSON knowledge base"""
        
        file_path = self.output_dir / f"{output_name}.json"
        
        # Convert to serializable format
        data = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_bookmarks": len(processed_bookmarks),
                "generator": "Bookmark AI Analyzer",
                "version": self.settings.app.version
            },
            "bookmarks": []
        }
        
        for bookmark in processed_bookmarks:
            bookmark_data = {
                "id": bookmark.bookmark_data.id,
                "url": bookmark.bookmark_data.url,
                "title": bookmark.bookmark_data.title,
                "content": bookmark.bookmark_data.content,
                "author": bookmark.bookmark_data.author,
                "created_at": bookmark.bookmark_data.created_at.isoformat(),
                "bookmark_type": bookmark.bookmark_data.bookmark_type,
                "categories": bookmark.categories,
                "tags": bookmark.tags,
                "processed_at": bookmark.processed_at.isoformat(),
                "processing_time": bookmark.processing_time
            }
            
            if self.include_metadata:
                bookmark_data["metadata"] = bookmark.bookmark_data.metadata
                bookmark_data["analysis_results"] = bookmark.analysis_results
            
            data["bookmarks"].append(bookmark_data)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return str(file_path)
    
    async def _generate_markdown(self, 
                               processed_bookmarks: List[ProcessedBookmark],
                               output_name: str) -> str:
        """Generate Markdown knowledge base"""
        
        file_path = self.output_dir / f"{output_name}.md"
        
        # Group bookmarks by category
        categorized_bookmarks = {}
        for bookmark in processed_bookmarks:
            primary_category = bookmark.categories[0] if bookmark.categories else "Uncategorized"
            if primary_category not in categorized_bookmarks:
                categorized_bookmarks[primary_category] = []
            categorized_bookmarks[primary_category].append(bookmark)
        
        # Generate markdown content
        md_content = []
        md_content.append(f"# {output_name.replace('_', ' ').title()}")
        md_content.append(f"\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md_content.append(f"Total bookmarks: {len(processed_bookmarks)}")
        md_content.append("\n---\n")
        
        # Table of Contents
        md_content.append("## Table of Contents\n")
        for category in sorted(categorized_bookmarks.keys()):
            md_content.append(f"- [{category}](#{category.lower().replace(' ', '-')})")
        md_content.append("\n---\n")
        
        # Content by category
        for category in sorted(categorized_bookmarks.keys()):
            bookmarks = categorized_bookmarks[category]
            md_content.append(f"## {category}\n")
            
            for bookmark in bookmarks:
                md_content.append(f"### {bookmark.bookmark_data.title}")
                md_content.append(f"**Author:** {bookmark.bookmark_data.author}")
                md_content.append(f"**URL:** [{bookmark.bookmark_data.url}]({bookmark.bookmark_data.url})")
                md_content.append(f"**Type:** {bookmark.bookmark_data.bookmark_type}")
                md_content.append(f"**Tags:** {', '.join(bookmark.tags)}")
                md_content.append(f"**Created:** {bookmark.bookmark_data.created_at.strftime('%Y-%m-%d')}")
                
                if bookmark.bookmark_data.content:
                    md_content.append(f"\n**Content:**")
                    md_content.append(f"{bookmark.bookmark_data.content[:500]}...")
                
                if self.include_metadata and bookmark.analysis_results:
                    analysis = bookmark.analysis_results.get('content_analysis', {})
                    if analysis:
                        md_content.append(f"\n**Key Insights:**")
                        insights = analysis.get('insights', [])
                        for insight in insights[:3]:  # Show top 3 insights
                            md_content.append(f"- {insight}")
                
                md_content.append("\n---\n")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_content))
        
        return str(file_path)
    
    async def _generate_csv(self, 
                          processed_bookmarks: List[ProcessedBookmark],
                          output_name: str) -> str:
        """Generate CSV knowledge base"""
        
        file_path = self.output_dir / f"{output_name}.csv"
        
        fieldnames = [
            'id', 'title', 'url', 'author', 'content', 'bookmark_type',
            'categories', 'tags', 'created_at', 'processed_at', 'processing_time'
        ]
        
        if self.include_metadata:
            fieldnames.extend(['metadata', 'analysis_results'])
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for bookmark in processed_bookmarks:
                row = {
                    'id': bookmark.bookmark_data.id,
                    'title': bookmark.bookmark_data.title,
                    'url': bookmark.bookmark_data.url,
                    'author': bookmark.bookmark_data.author,
                    'content': bookmark.bookmark_data.content[:1000],  # Truncate for CSV
                    'bookmark_type': bookmark.bookmark_data.bookmark_type,
                    'categories': '; '.join(bookmark.categories),
                    'tags': '; '.join(bookmark.tags),
                    'created_at': bookmark.bookmark_data.created_at.isoformat(),
                    'processed_at': bookmark.processed_at.isoformat(),
                    'processing_time': bookmark.processing_time
                }
                
                if self.include_metadata:
                    row['metadata'] = json.dumps(bookmark.bookmark_data.metadata)
                    row['analysis_results'] = json.dumps(bookmark.analysis_results)
                
                writer.writerow(row)
        
        return str(file_path)
    
    async def _generate_statistics(self, 
                                 processed_bookmarks: List[ProcessedBookmark],
                                 output_name: str) -> str:
        """Generate statistics file"""
        
        file_path = self.output_dir / f"{output_name}_statistics.json"
        
        # Calculate statistics
        stats = {
            "generation_metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_bookmarks": len(processed_bookmarks),
                "generator": "Bookmark AI Analyzer",
                "version": self.settings.app.version
            },
            "content_statistics": {
                "bookmark_types": {},
                "categories": {},
                "tags": {},
                "authors": {},
                "processing_times": {
                    "total": 0,
                    "average": 0,
                    "min": float('inf'),
                    "max": 0
                }
            }
        }
        
        # Count bookmark types
        for bookmark in processed_bookmarks:
            bookmark_type = bookmark.bookmark_data.bookmark_type
            stats["content_statistics"]["bookmark_types"][bookmark_type] = \
                stats["content_statistics"]["bookmark_types"].get(bookmark_type, 0) + 1
        
        # Count categories
        for bookmark in processed_bookmarks:
            for category in bookmark.categories:
                stats["content_statistics"]["categories"][category] = \
                    stats["content_statistics"]["categories"].get(category, 0) + 1
        
        # Count tags
        for bookmark in processed_bookmarks:
            for tag in bookmark.tags:
                stats["content_statistics"]["tags"][tag] = \
                    stats["content_statistics"]["tags"].get(tag, 0) + 1
        
        # Count authors
        for bookmark in processed_bookmarks:
            author = bookmark.bookmark_data.author
            if author:
                stats["content_statistics"]["authors"][author] = \
                    stats["content_statistics"]["authors"].get(author, 0) + 1
        
        # Calculate processing time statistics
        processing_times = [bookmark.processing_time for bookmark in processed_bookmarks]
        if processing_times:
            stats["content_statistics"]["processing_times"]["total"] = sum(processing_times)
            stats["content_statistics"]["processing_times"]["average"] = sum(processing_times) / len(processing_times)
            stats["content_statistics"]["processing_times"]["min"] = min(processing_times)
            stats["content_statistics"]["processing_times"]["max"] = max(processing_times)
        
        # Sort by frequency
        for key in ["bookmark_types", "categories", "tags", "authors"]:
            stats["content_statistics"][key] = dict(
                sorted(stats["content_statistics"][key].items(), 
                      key=lambda x: x[1], reverse=True)
            )
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        return str(file_path)
    
    async def generate_ai_training_data(self, 
                                      processed_bookmarks: List[ProcessedBookmark],
                                      output_name: str = "ai_training_data") -> str:
        """Generate training data format for AI models"""
        
        file_path = self.output_dir / f"{output_name}.jsonl"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            for bookmark in processed_bookmarks:
                training_sample = {
                    "input": bookmark.bookmark_data.content,
                    "output": {
                        "categories": bookmark.categories,
                        "tags": bookmark.tags,
                        "analysis": bookmark.analysis_results
                    },
                    "metadata": {
                        "url": bookmark.bookmark_data.url,
                        "title": bookmark.bookmark_data.title,
                        "author": bookmark.bookmark_data.author,
                        "type": bookmark.bookmark_data.bookmark_type
                    }
                }
                
                f.write(json.dumps(training_sample, ensure_ascii=False) + '\n')
        
        return str(file_path)
    
    def get_generated_files(self) -> List[str]:
        """Get list of all generated files"""
        return [str(p) for p in self.output_dir.glob("*") if p.is_file()]