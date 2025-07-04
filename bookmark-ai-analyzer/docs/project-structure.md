# Bookmark AI Analyzer - Project Structure

## Overview

This project implements a comprehensive system for analyzing X/Twitter bookmarks using multiple LLM providers to create a structured knowledge base.

## Project Structure

```
bookmark-ai-analyzer/
├── src/                      # Source code
│   ├── config/              # Configuration management
│   │   ├── settings.py      # Settings and configuration classes
│   │   └── llm_configs.yaml # LLM provider configurations
│   ├── core/                # Core processing modules
│   │   ├── bookmark_processor.py    # Main processing orchestration
│   │   ├── content_extractor.py     # Content extraction logic
│   │   └── knowledge_base_generator.py # Knowledge base generation
│   ├── llm/                 # LLM client implementations
│   │   ├── base_client.py   # Abstract base class for LLM clients
│   │   ├── claude_client.py # Claude (Anthropic) implementation
│   │   ├── gemini_client.py # Google Gemini implementation
│   │   └── grok_client.py   # Grok (X.AI) implementation
│   ├── analyzers/           # Content analysis modules
│   │   ├── content_analyzer.py # Content analysis logic
│   │   ├── categorizer.py   # Categorization system
│   │   └── tagger.py        # Tagging system
│   ├── extractors/          # Content extractors
│   │   ├── tweet_extractor.py  # Tweet extraction
│   │   ├── thread_extractor.py # Thread reconstruction
│   │   └── video_extractor.py  # Video content extraction
│   └── utils/               # Utility modules
│       ├── logger.py        # Logging configuration
│       ├── checkpoint_manager.py # Checkpoint/resume functionality
│       └── validation.py    # Data validation utilities
├── tests/                   # Test suite
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── fixtures/           # Test data
├── data/                   # Data directories
│   ├── raw/               # Raw bookmark data
│   ├── processed/         # Processed outputs
│   └── knowledge_base/    # Generated knowledge base
├── config/                # Configuration files
│   ├── development.yaml   # Development settings
│   ├── production.yaml    # Production settings
│   └── test.yaml         # Test settings
├── scripts/              # Utility scripts
│   ├── setup.py         # Project setup script
│   └── run_analysis.py  # Main execution script
├── requirements.txt     # Python dependencies
├── requirements-dev.txt # Development dependencies
├── pytest.ini          # Pytest configuration
├── .gitignore         # Git ignore rules
└── README.md          # Project documentation
```

## Key Components

### 1. Configuration System (`src/config/`)
- **settings.py**: Pydantic-based configuration management
- Supports multiple environments (dev, prod, test)
- Environment variable overrides
- YAML-based configuration files

### 2. LLM Clients (`src/llm/`)
- **Base Client**: Abstract interface with rate limiting, retry logic, and metrics
- **Claude Client**: Optimized for deep content analysis
- **Gemini Client**: Multimodal capabilities for images/video
- **Grok Client**: Specialized for X/Twitter content analysis

### 3. Utility Modules (`src/utils/`)
- **Logger**: Structured logging with Loguru
- **Checkpoint Manager**: Resume interrupted processing
- **Validation**: Content quality and spam detection

### 4. Processing Pipeline
1. **Content Extraction**: Extract bookmarks from CSV/JSON
2. **LLM Analysis**: Analyze content using appropriate LLM
3. **Categorization**: Automatic categorization and tagging
4. **Knowledge Base**: Generate structured knowledge base
5. **Export**: Multiple export formats (Anki, Notion, etc.)

## Features Implemented

✅ Modular architecture with clear separation of concerns
✅ Multi-LLM support with fallback mechanisms
✅ Comprehensive configuration system
✅ Advanced logging and monitoring
✅ Checkpoint/resume functionality
✅ Content validation and quality assessment
✅ Rate limiting and retry logic
✅ Async/await for performance

## Next Steps

The following components need to be implemented:
1. Content extractors (tweet, thread, video)
2. Analyzers (categorizer, tagger)
3. Knowledge base generator
4. Main bookmark processor
5. Export functionality
6. Test suite

## Usage

```bash
# Setup project
python scripts/setup.py

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.template .env
# Edit .env with your API keys

# Run analysis
python -m bookmark_analyzer process --input bookmarks.csv
```