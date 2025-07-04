"""Command-line interface for bookmark analyzer."""

import asyncio
import click
from pathlib import Path
from typing import Optional, List
import sys

from .core import BookmarkProcessor
from .utils.logger import get_logger, setup_logging
from .config import get_settings

logger = get_logger(__name__)


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool):
    """X/Twitter Bookmark AI Analyzer - Transform your bookmarks into structured knowledge."""
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(log_level)
    
    # Store config path in context
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = Path(config) if config else None
    ctx.obj['verbose'] = verbose


@cli.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.argument('output_dir', type=click.Path())
@click.option('--format', '-f', 'export_formats', multiple=True, 
              type=click.Choice(['json', 'anki', 'notion', 'obsidian']),
              default=['json'], help='Export formats')
@click.option('--no-resume', is_flag=True, help='Start fresh, ignore checkpoints')
@click.option('--no-videos', is_flag=True, help='Skip video extraction')
@click.option('--no-threads', is_flag=True, help='Skip thread reconstruction')
@click.option('--depth', type=click.Choice(['quick', 'standard', 'comprehensive']),
              default='comprehensive', help='Analysis depth')
@click.pass_context
def process(ctx, input_file: str, output_dir: str, export_formats: List[str],
            no_resume: bool, no_videos: bool, no_threads: bool, depth: str):
    """Process bookmarks from input file."""
    input_path = Path(input_file)
    output_path = Path(output_dir)
    
    # Update settings if needed
    if ctx.obj.get('config_path'):
        settings = get_settings(ctx.obj['config_path'])
    else:
        settings = get_settings()
    
    # Override settings from CLI
    settings.processing.enable_video_extraction = not no_videos
    settings.processing.enable_thread_reconstruction = not no_threads
    settings.processing.analysis_depth = depth
    
    # Create processor
    processor = BookmarkProcessor(config_path=ctx.obj.get('config_path'))
    
    # Run processing
    click.echo(f"Processing bookmarks from {input_file}")
    click.echo(f"Output directory: {output_dir}")
    click.echo(f"Export formats: {', '.join(export_formats)}")
    
    try:
        # Run async processing
        report = asyncio.run(processor.process_bookmarks(
            input_path,
            output_path,
            resume=not no_resume,
            export_formats=list(export_formats)
        ))
        
        # Display summary
        click.echo("\n" + "="*50)
        click.echo("PROCESSING COMPLETE")
        click.echo("="*50)
        click.echo(f"Status: {report['summary']['status']}")
        click.echo(f"Duration: {report['summary']['duration_formatted']}")
        click.echo(f"Total items processed: {report['summary']['total_items_processed']}")
        
        if report['errors']:
            click.echo(f"\nErrors ({len(report['errors'])}):")
            for error in report['errors'][:5]:
                click.echo(f"  - {error}")
        
        click.echo(f"\nFull report saved to: {output_path / 'processing_report.json'}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if ctx.obj['verbose']:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate configuration and test connections."""
    processor = BookmarkProcessor(config_path=ctx.obj.get('config_path'))
    
    click.echo("Validating configuration...")
    
    try:
        results = asyncio.run(processor.validate_configuration())
        
        click.echo(f"\nConfiguration valid: {results['valid']}")
        
        click.echo("\nLLM Provider Status:")
        for provider, status in results['llm_status'].items():
            symbol = "✓" if status == "active" else "✗"
            click.echo(f"  {symbol} {provider}: {status}")
        
        if results['errors']:
            click.echo("\nErrors:")
            for error in results['errors']:
                click.echo(f"  - {error}")
        
        if results['warnings']:
            click.echo("\nWarnings:")
            for warning in results['warnings']:
                click.echo(f"  - {warning}")
        
        if not results['valid']:
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"Validation failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def checkpoints(ctx):
    """List available checkpoints."""
    processor = BookmarkProcessor(config_path=ctx.obj.get('config_path'))
    
    checkpoints = processor.list_checkpoints()
    
    if not checkpoints:
        click.echo("No checkpoints found.")
        return
    
    click.echo("Available checkpoints:")
    click.echo("-" * 80)
    
    for cp in checkpoints:
        status_symbol = "✓" if cp['is_complete'] else "○"
        click.echo(
            f"{status_symbol} {cp['checkpoint_id'][:20]}... | "
            f"Created: {cp['created_at']} | "
            f"Status: {cp['status']} | "
            f"Progress: {cp.get('progress', 'N/A')}"
        )


@cli.command()
@click.argument('url')
@click.option('--analyze/--no-analyze', default=True, help='Perform analysis')
@click.option('--output', '-o', type=click.Path(), help='Output file')
@click.pass_context
def single(ctx, url: str, analyze: bool, output: Optional[str]):
    """Process a single bookmark URL."""
    processor = BookmarkProcessor(config_path=ctx.obj.get('config_path'))
    
    bookmark_data = {
        'url': url,
        'id': url.split('/')[-1],  # Simple ID extraction
    }
    
    click.echo(f"Processing single bookmark: {url}")
    
    try:
        result = asyncio.run(processor.process_single_bookmark(bookmark_data, analyze))
        
        if output:
            import json
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            click.echo(f"Result saved to: {output}")
        else:
            # Display summary
            if result:
                click.echo(f"\nTitle: {result.get('title', 'N/A')}")
                click.echo(f"Type: {result.get('type', 'N/A')}")
                if analyze:
                    click.echo(f"Category: {result.get('categorization', {}).get('primary_category', 'N/A')}")
                    click.echo(f"Tags: {', '.join(result.get('categorization', {}).get('tags', []))}")
                    click.echo(f"Quality Score: {result.get('quality', {}).get('overall_score', 'N/A')}")
                
    except Exception as e:
        click.echo(f"Error processing bookmark: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--example', type=click.Choice(['minimal', 'full']), 
              default='minimal', help='Example type to generate')
def init(example: str):
    """Initialize configuration files with examples."""
    from .config import create_example_config
    
    config_dir = Path('config')
    config_dir.mkdir(exist_ok=True)
    
    # Create example config
    config_file = config_dir / 'development.yaml'
    if config_file.exists():
        click.confirm(f"{config_file} already exists. Overwrite?", abort=True)
    
    create_example_config(config_file, example_type=example)
    click.echo(f"Created example configuration: {config_file}")
    
    # Create example input files
    examples_dir = Path('examples')
    examples_dir.mkdir(exist_ok=True)
    
    # Create example CSV
    csv_example = examples_dir / 'bookmarks_example.csv'
    with open(csv_example, 'w', encoding='utf-8') as f:
        f.write("url,title,author,created_at\n")
        f.write('https://twitter.com/user/status/123,"Example tweet about Python",user,2024-01-01\n')
        f.write('https://youtube.com/watch?v=abc,"Python Tutorial Video",channel,2024-01-02\n')
    
    click.echo(f"Created example CSV: {csv_example}")
    
    # Create example JSON
    json_example = examples_dir / 'bookmarks_example.json'
    import json
    example_data = [
        {
            "id": "123",
            "url": "https://twitter.com/user/status/123",
            "content": "This is an example tweet about #Python programming",
            "author": "user",
            "created_at": "2024-01-01T12:00:00Z"
        },
        {
            "id": "456",
            "url": "https://youtube.com/watch?v=abc",
            "title": "Python Tutorial",
            "description": "Learn Python basics",
            "author": "channel"
        }
    ]
    
    with open(json_example, 'w', encoding='utf-8') as f:
        json.dump(example_data, f, indent=2)
    
    click.echo(f"Created example JSON: {json_example}")
    
    click.echo("\nTo get started:")
    click.echo(f"1. Edit {config_file} with your API keys")
    click.echo(f"2. Run: bookmark-analyzer process {csv_example} output/")


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main()