#!/bin/bash
# Quickstart script for Bookmark AI Analyzer

echo "🚀 Bookmark AI Analyzer - Quick Start"
echo "===================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1)
if [[ $? -ne 0 ]]; then
    echo "❌ Python 3 is not installed. Please install Python 3.9 or higher."
    exit 1
fi
echo "✅ $python_version"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -e .
echo "✅ Dependencies installed"
echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p config data/raw data/processed logs checkpoints examples
echo "✅ Directories created"
echo ""

# Initialize configuration
echo "Initializing configuration..."
if [ ! -f "config/development.yaml" ]; then
    python -m src.cli init
    echo "✅ Configuration initialized"
else
    echo "✅ Configuration already exists"
fi
echo ""

# Download NLTK data
echo "Downloading NLTK data..."
python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('stopwords', quiet=True); nltk.download('averaged_perceptron_tagger', quiet=True)"
echo "✅ NLTK data downloaded"
echo ""

echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit config/development.yaml with your API keys"
echo "2. Run: bookmark-analyzer process examples/bookmarks_example.csv output/"
echo ""
echo "For help: bookmark-analyzer --help"