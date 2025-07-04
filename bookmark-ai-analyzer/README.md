# Bookmark AI Analyzer

An advanced system for analyzing X/Twitter bookmarks using multiple LLM providers to create a structured knowledge base.

## Features

- 🤖 Multi-LLM support (Grok, Claude, Gemini)
- 📊 Advanced content analysis and categorization
- 🏷️ Intelligent tagging system
- 📚 Knowledge base generation
- 🎯 Learning path creation
- 📈 Progress tracking with checkpoints
- 🔄 Batch processing with resume capability
- 📤 Multiple export formats (Anki, Notion, Obsidian)

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/bookmark-ai-analyzer.git
cd bookmark-ai-analyzer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. Copy the example configuration:
```bash
cp config/development.yaml.example config/development.yaml
```

2. Add your API keys:
```yaml
llm:
  grok:
    api_key: "your-grok-api-key"
  claude:
    api_key: "your-claude-api-key"
  gemini:
    api_key: "your-gemini-api-key"
```

### Basic Usage

```bash
# Process bookmarks from CSV
python -m bookmark_analyzer process --input bookmarks.csv --config config/development.yaml

# Resume from checkpoint
python -m bookmark_analyzer resume --checkpoint latest

# Export to specific format
python -m bookmark_analyzer export --format anki --category programming

# View processing statistics
python -m bookmark_analyzer stats --period 30d
```

## Architecture

The system follows a modular architecture with clear separation of concerns:

- **Extractors**: Handle different content types (tweets, threads, videos)
- **Analyzers**: Perform content analysis and categorization
- **LLM Clients**: Interface with various AI providers
- **Knowledge Base**: Generate structured learning materials
- **Export**: Support multiple output formats

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test category
pytest tests/unit/
pytest tests/integration/
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
flake8 src/ tests/

# Type checking
mypy src/
```

## Documentation

- [Architecture Guide](docs/architecture.md)
- [Configuration Guide](docs/configuration.md)
- [API Reference](docs/api.md)
- [Troubleshooting](docs/troubleshooting.md)

## License

MIT License - see [LICENSE](LICENSE) file for details.