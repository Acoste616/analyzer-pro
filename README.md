# 🔖 Bookmark AI Analyzer

An advanced, modular system for analyzing X/Twitter bookmarks with AI-powered content analysis, categorization, and knowledge base generation.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## ✨ Features

### 🧠 AI-Powered Analysis
- **Multi-LLM Support**: Integrates with Grok, Claude, and Gemini APIs
- **Content Analysis**: Extracts key insights, topics, and actionable items
- **Smart Categorization**: Hierarchical categorization with confidence scores
- **Intelligent Tagging**: Automatic tag generation with semantic understanding

### 🔄 Advanced Processing
- **Async Processing**: High-performance asynchronous operations
- **Checkpoint System**: Resume long-running processes from interruptions
- **Rate Limiting**: Built-in API rate limiting and retry mechanisms
- **Batch Processing**: Efficient processing of large bookmark collections

### 📊 Multi-Platform Content Extraction
- **Twitter/X**: Tweets, threads, engagement metrics
- **YouTube**: Video metadata, descriptions, transcripts
- **Web Content**: Articles, blogs, documentation
- **Generic URLs**: Fallback extraction for any webpage

### 📖 Knowledge Base Generation
- **Multiple Formats**: JSON, Markdown, CSV outputs
- **Training Data**: AI-ready datasets for model fine-tuning
- **Rich Metadata**: Comprehensive analytics and statistics
- **Export Options**: Flexible output customization

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- API keys for desired LLM providers (Grok, Claude, Gemini)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/bookmark-ai-analyzer.git
cd bookmark-ai-analyzer
```

2. **Run the setup script**
```bash
python scripts/setup.py --dev
```

3. **Activate the virtual environment**
```bash
# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

4. **Configure API keys**
```bash
# Edit the .env file with your API keys
nano .env
```

### Basic Usage

**Analyze sample bookmarks:**
```bash
python scripts/run_analysis.py --sample
```

**Analyze your bookmarks:**
```bash
python scripts/run_analysis.py --input bookmarks.json --output results/
```

**Advanced processing with checkpoints:**
```bash
python scripts/run_analysis.py \
  --input large_bookmarks.json \
  --checkpoint \
  --max-workers 8 \
  --batch-size 20 \
  --formats json markdown csv
```

## 📋 Project Structure

```
bookmark-ai-analyzer/
├── src/                          # Source code
│   ├── config/                   # Configuration management
│   │   ├── settings.py          # Settings classes and manager
│   │   └── llm_configs.yaml     # LLM provider configurations
│   ├── core/                     # Core processing modules
│   │   ├── bookmark_processor.py # Main processing engine
│   │   ├── content_extractor.py  # Content extraction framework
│   │   └── knowledge_base_generator.py # Output generation
│   ├── llm/                      # LLM client implementations
│   │   ├── base_client.py       # Abstract base client
│   │   ├── grok_client.py       # Grok/X AI integration
│   │   ├── claude_client.py     # Anthropic Claude integration
│   │   └── gemini_client.py     # Google Gemini integration
│   ├── analyzers/               # Analysis modules
│   │   ├── content_analyzer.py  # Content analysis with LLMs
│   │   ├── categorizer.py       # Hierarchical categorization
│   │   └── tagger.py           # Intelligent tag generation
│   ├── extractors/              # Content extractors
│   │   ├── tweet_extractor.py   # Twitter/X content extraction
│   │   ├── thread_extractor.py  # Twitter thread processing
│   │   └── video_extractor.py   # Video platform extraction
│   └── utils/                   # Utility modules
│       ├── logger.py            # Advanced logging system
│       ├── checkpoint_manager.py # Checkpoint management
│       └── validation.py        # Data validation
├── tests/                       # Test suite
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── fixtures/                # Test data and fixtures
├── config/                      # Configuration files
│   ├── development.yaml         # Development settings
│   ├── production.yaml          # Production settings
│   └── test.yaml               # Test settings
├── scripts/                     # Utility scripts
│   ├── setup.py                # Project setup script
│   └── run_analysis.py         # Main analysis script
└── data/                       # Data directories
    ├── raw/                    # Raw input data
    ├── processed/              # Processed data
    ├── knowledge_base/         # Generated knowledge bases
    └── checkpoints/           # Processing checkpoints
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with your configuration:

```env
# LLM API Keys
ANTHROPIC_API_KEY=your_claude_api_key
GEMINI_API_KEY=your_gemini_api_key
GROK_API_KEY=your_grok_api_key

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO

# Processing
MAX_WORKERS=4
BATCH_SIZE=10
```

### Configuration Files

Customize behavior through YAML configuration files:

```yaml
# config/development.yaml
app:
  name: "Bookmark AI Analyzer"
  environment: "development"
  debug: true

processing:
  batch_size: 10
  max_workers: 4
  checkpoint_interval: 50

analysis:
  default_llm_provider: "claude"
  enable_content_analysis: true
  enable_categorization: true
  enable_tagging: true
```

## 🔌 API Integration

### Supported LLM Providers

| Provider | Models | Features |
|----------|--------|----------|
| **Grok** | grok-beta | Function calling, structured output |
| **Claude** | claude-3-sonnet | Tool use, image analysis |
| **Gemini** | gemini-1.5-pro | Multimodal, token counting |

### Rate Limiting

Built-in rate limiting respects API limits:

```python
# Automatic rate limiting
rate_limiter = RateLimiter(
    requests_per_minute=60,
    tokens_per_minute=200000
)
```

## 📊 Analysis Features

### Content Analysis

Extract comprehensive insights from bookmarks:

```python
analysis_result = await analyzer.analyze(content)
# Returns: topics, insights, actionable items, technologies, expertise level
```

### Categorization

Hierarchical categorization with confidence scores:

```python
categories = await categorizer.categorize(content)
# Returns: ["Technology", "Programming", "Python"]
```

### Tagging

Intelligent tag generation:

```python
tags = await tagger.generate_tags(content)
# Returns: ["python", "machine-learning", "tutorial", "beginner"]
```

## 🎯 Use Cases

### Personal Knowledge Management
- Analyze your Twitter bookmarks to build a personal knowledge base
- Categorize and tag content for easy retrieval
- Generate summaries and extract key insights

### Content Curation
- Process large volumes of bookmarked content
- Identify trends and popular topics
- Create curated lists based on categories and quality scores

### Research and Analysis
- Extract insights from social media discussions
- Analyze content patterns and themes
- Generate training data for AI models

### Team Knowledge Sharing
- Process team-wide bookmark collections
- Generate searchable knowledge bases
- Share insights and recommendations

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests only
pytest -m slow          # Long-running tests

# Run with coverage
pytest --cov=src --cov-report=html
```

### Test Categories

- **Unit Tests**: Test individual components
- **Integration Tests**: Test component interactions
- **Benchmark Tests**: Performance testing
- **External Tests**: Tests requiring API keys

## 🔧 Development

### Code Quality

The project uses modern Python development practices:

```bash
# Format code
black .
isort .

# Linting
flake8 src/
pylint src/

# Type checking
mypy src/

# Security analysis
bandit -r src/
```

### Pre-commit Hooks

Install pre-commit hooks for automatic code quality checks:

```bash
pre-commit install
```

## 📈 Performance

### Benchmarks

- **Processing Speed**: ~100-500 bookmarks/minute (depending on LLM)
- **Memory Usage**: ~200-500MB for typical workloads
- **Concurrent Processing**: Up to 20 concurrent LLM requests

### Optimization Tips

1. **Use Checkpoints**: For large datasets (>1000 bookmarks)
2. **Adjust Batch Size**: Optimize for your hardware and API limits
3. **Enable Caching**: Reuse analysis results when possible
4. **Monitor Rate Limits**: Balance speed vs API costs

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Install development dependencies: `pip install -r requirements-dev.txt`
4. Run tests: `pytest`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI, Anthropic, Google**: For providing powerful LLM APIs
- **aiohttp**: For async HTTP client capabilities
- **pytest**: For comprehensive testing framework
- **Rich**: For beautiful terminal output

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/bookmark-ai-analyzer/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/bookmark-ai-analyzer/discussions)
- **Documentation**: [Wiki](https://github.com/yourusername/bookmark-ai-analyzer/wiki)

## 🗺️ Roadmap

### Near Term (v1.1)
- [ ] Browser extension for direct bookmark import
- [ ] Web interface for easier usage
- [ ] Additional LLM provider support (OpenAI GPT-4)
- [ ] Enhanced video content analysis

### Medium Term (v1.5)
- [ ] Real-time bookmark monitoring
- [ ] Collaborative filtering and recommendations
- [ ] Advanced analytics dashboard
- [ ] API server mode

### Long Term (v2.0)
- [ ] Custom model fine-tuning
- [ ] Multi-language support
- [ ] Enterprise features and deployment
- [ ] Mobile app integration

---

**Made with ❤️ for the knowledge management community**