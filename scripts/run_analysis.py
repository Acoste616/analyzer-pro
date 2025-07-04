#!/usr/bin/env python3
"""
Main script to run bookmark analysis
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.bookmark_processor import BookmarkProcessor
from src.core.knowledge_base_generator import KnowledgeBaseGenerator
from src.config.settings import settings_manager
from src.utils.logger import get_logger, set_log_level
from src.utils.validation import validate_bookmark_data


def load_bookmarks_from_file(file_path: str) -> List[Dict[str, Any]]:
    """Load bookmarks from a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle different input formats
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and 'bookmarks' in data:
            return data['bookmarks']
        else:
            raise ValueError("Invalid bookmark file format")
    
    except Exception as e:
        print(f"❌ Error loading bookmarks from {file_path}: {str(e)}")
        return []


def create_sample_bookmarks() -> List[Dict[str, Any]]:
    """Create sample bookmarks for demonstration."""
    return [
        {
            "id": "sample_001",
            "url": "https://example.com/ai-trends-2024",
            "title": "AI Trends to Watch in 2024",
            "content": "Artificial intelligence continues to evolve rapidly, with new breakthroughs in machine learning, natural language processing, and computer vision.",
            "author": "Tech Blogger",
            "created_at": "2024-01-15T10:00:00Z",
            "metadata": {
                "source": "tech_blog",
                "reading_time": 5
            }
        },
        {
            "id": "sample_002",
            "url": "https://example.com/python-best-practices",
            "title": "Python Best Practices for 2024",
            "content": "Learn the latest Python best practices including type hints, async programming, and modern development workflows.",
            "author": "Python Developer",
            "created_at": "2024-01-10T14:30:00Z",
            "metadata": {
                "source": "dev_community",
                "tags": ["python", "programming", "best-practices"]
            }
        },
        {
            "id": "sample_003",
            "url": "https://youtube.com/watch?v=example123",
            "title": "Machine Learning Tutorial - Complete Guide",
            "content": "A comprehensive tutorial covering machine learning fundamentals, from basic concepts to advanced techniques.",
            "author": "ML Educator",
            "created_at": "2024-01-05T09:15:00Z",
            "metadata": {
                "source": "youtube",
                "duration": 3600,
                "video_type": "tutorial"
            }
        }
    ]


def validate_bookmarks(bookmarks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and filter bookmarks."""
    valid_bookmarks = []
    
    for i, bookmark in enumerate(bookmarks):
        if validate_bookmark_data(bookmark):
            valid_bookmarks.append(bookmark)
        else:
            print(f"⚠️  Skipping invalid bookmark at index {i}: {bookmark.get('id', 'unknown')}")
    
    return valid_bookmarks


def progress_callback(current: int, total: int):
    """Progress callback function."""
    percentage = (current / total) * 100
    print(f"📊 Processing: {current}/{total} ({percentage:.1f}%)")


def error_callback(error: Exception, context: Dict[str, Any]):
    """Error callback function."""
    print(f"❌ Error: {str(error)}")
    if context:
        print(f"   Context: {context}")


async def main():
    """Main analysis function."""
    parser = argparse.ArgumentParser(description="Bookmark AI Analyzer")
    parser.add_argument("--input", "-i", 
                       help="Input JSON file containing bookmarks")
    parser.add_argument("--output", "-o", default="output",
                       help="Output directory (default: output)")
    parser.add_argument("--sample", action="store_true",
                       help="Use sample bookmarks for demonstration")
    parser.add_argument("--config", "-c",
                       help="Configuration file path")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level")
    parser.add_argument("--max-workers", type=int, default=4,
                       help="Maximum number of worker processes")
    parser.add_argument("--batch-size", type=int, default=10,
                       help="Batch size for processing")
    parser.add_argument("--no-analysis", action="store_true",
                       help="Skip content analysis (faster processing)")
    parser.add_argument("--no-categorization", action="store_true",
                       help="Skip categorization")
    parser.add_argument("--no-tagging", action="store_true",
                       help="Skip tagging")
    parser.add_argument("--checkpoint", action="store_true",
                       help="Enable checkpointing for long processes")
    parser.add_argument("--resume", 
                       help="Resume from checkpoint ID")
    parser.add_argument("--formats", nargs="+", 
                       default=["json", "markdown"],
                       choices=["json", "markdown", "csv"],
                       help="Output formats")
    
    args = parser.parse_args()
    
    # Setup logging
    set_log_level(args.log_level)
    logger = get_logger(__name__)
    
    print("🚀 Bookmark AI Analyzer")
    print("=" * 50)
    
    # Load configuration
    if args.config:
        # TODO: Load custom config
        logger.info(f"Loading config from {args.config}")
    
    # Load bookmarks
    if args.sample:
        print("📚 Using sample bookmarks...")
        bookmarks = create_sample_bookmarks()
    elif args.input:
        print(f"📁 Loading bookmarks from {args.input}...")
        bookmarks = load_bookmarks_from_file(args.input)
        if not bookmarks:
            print("❌ No bookmarks loaded. Exiting.")
            return
    else:
        print("❌ Please provide --input file or use --sample")
        return
    
    # Validate bookmarks
    print(f"✅ Validating {len(bookmarks)} bookmarks...")
    valid_bookmarks = validate_bookmarks(bookmarks)
    
    if not valid_bookmarks:
        print("❌ No valid bookmarks found. Exiting.")
        return
    
    print(f"📝 Processing {len(valid_bookmarks)} valid bookmarks...")
    
    # Configure processor
    processor = BookmarkProcessor(
        progress_callback=progress_callback,
        error_callback=error_callback
    )
    
    # Update settings based on args
    settings = settings_manager.settings
    if args.max_workers:
        settings.processing.max_workers = args.max_workers
    if args.batch_size:
        settings.processing.batch_size = args.batch_size
    if args.no_analysis:
        settings.analysis.enable_content_analysis = False
    if args.no_categorization:
        settings.analysis.enable_categorization = False
    if args.no_tagging:
        settings.analysis.enable_tagging = False
    
    try:
        # Process bookmarks
        start_time = datetime.now()
        print(f"⚡ Starting analysis at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        checkpoint_key = args.resume or ("bookmark_analysis_" + start_time.strftime('%Y%m%d_%H%M%S'))
        
        if args.resume:
            print(f"🔄 Resuming from checkpoint: {args.resume}")
        
        results = await processor.process_bookmarks(
            valid_bookmarks,
            checkpoint_key=checkpoint_key if args.checkpoint or args.resume else None
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"✅ Analysis completed in {duration:.2f} seconds")
        print(f"📊 Processed {len(results)} bookmarks")
        
        # Generate statistics
        stats = processor.get_processing_stats()
        print(f"   - Successful: {stats.get('successful', 0)}")
        print(f"   - Failed: {stats.get('failed', 0)}")
        print(f"   - Skipped: {stats.get('skipped', 0)}")
        
        # Generate knowledge base
        if results:
            print(f"📖 Generating knowledge base...")
            
            # Create output directory
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Update knowledge base settings
            kb_settings = settings_manager.settings.knowledge_base
            kb_settings.output_dir = str(output_dir)
            kb_settings.formats = args.formats
            
            generator = KnowledgeBaseGenerator()
            
            # Generate output files
            output_name = f"bookmark_analysis_{start_time.strftime('%Y%m%d_%H%M%S')}"
            generated_files = await generator.generate_knowledge_base(results, output_name)
            
            print(f"📁 Generated files:")
            for format_type, file_path in generated_files.items():
                print(f"   - {format_type}: {file_path}")
            
            # Generate AI training data
            if len(results) > 10:  # Only if we have enough data
                training_file = await generator.generate_ai_training_data(results, f"{output_name}_training")
                print(f"   - AI training data: {training_file}")
        
        print(f"\n🎉 Analysis complete! Results saved to: {args.output}")
        
    except KeyboardInterrupt:
        print("\n⚠️  Analysis interrupted by user")
        if args.checkpoint:
            print(f"📁 Progress saved in checkpoint: {checkpoint_key}")
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        print(f"❌ Analysis failed: {str(e)}")
        sys.exit(1)


def cli():
    """CLI entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    cli()