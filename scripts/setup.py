#!/usr/bin/env python3
"""
Setup script for Bookmark AI Analyzer
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import yaml


def run_command(command, description, check=True):
    """Run a shell command with error handling."""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=check, capture_output=True, text=True)
        if result.stdout:
            print(f"   {result.stdout.strip()}")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stdout:
            print(f"   stdout: {e.stdout}")
        if e.stderr:
            print(f"   stderr: {e.stderr}")
        return False


def check_python_version():
    """Check if Python version is compatible."""
    print("🐍 Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher is required!")
        return False
    
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")
    return True


def create_virtual_environment(venv_path="venv"):
    """Create a virtual environment."""
    if Path(venv_path).exists():
        print(f"📁 Virtual environment '{venv_path}' already exists")
        return True
    
    return run_command(f"python -m venv {venv_path}", 
                      f"Creating virtual environment '{venv_path}'")


def install_dependencies(dev=False, venv_path="venv"):
    """Install project dependencies."""
    pip_cmd = f"{venv_path}/bin/pip" if os.name != 'nt' else f"{venv_path}\\Scripts\\pip.exe"
    
    # Upgrade pip first
    if not run_command(f"{pip_cmd} install --upgrade pip", "Upgrading pip"):
        return False
    
    # Install requirements
    requirements_file = "requirements-dev.txt" if dev else "requirements.txt"
    return run_command(f"{pip_cmd} install -r {requirements_file}", 
                      f"Installing {'development' if dev else 'production'} dependencies")


def create_directories():
    """Create necessary project directories."""
    directories = [
        "logs",
        "data/raw",
        "data/processed", 
        "data/knowledge_base",
        "data/checkpoints",
        "config",
        "tests/fixtures"
    ]
    
    print("📂 Creating project directories...")
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"   Created: {directory}")
    
    return True


def create_environment_file():
    """Create a sample .env file."""
    env_file = Path(".env")
    if env_file.exists():
        print("📝 .env file already exists")
        return True
    
    env_content = """# Bookmark AI Analyzer Environment Configuration

# Environment
ENVIRONMENT=development
DEBUG=true

# LLM API Keys (add your actual keys)
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
GROK_API_KEY=your_grok_api_key_here

# Database (for production)
DATABASE_URL=postgresql://user:password@localhost/bookmark_analyzer

# Redis (for caching)
REDIS_URL=redis://localhost:6379/0

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/bookmark_analyzer.log

# Processing
MAX_WORKERS=4
BATCH_SIZE=10
CHECKPOINT_INTERVAL=50

# Security
SECRET_KEY=your_secret_key_here

# External Services
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here
YOUTUBE_API_KEY=your_youtube_api_key_here
"""
    
    env_file.write_text(env_content)
    print("📝 Created .env file with sample configuration")
    print("   ⚠️  Please update the API keys and other sensitive values!")
    return True


def setup_git_hooks():
    """Setup pre-commit hooks."""
    if not Path(".git").exists():
        print("📝 Git repository not found, skipping git hooks setup")
        return True
    
    return run_command("pre-commit install", "Setting up pre-commit hooks", check=False)


def create_sample_config():
    """Create a sample configuration file."""
    config_file = Path("config/sample.yaml")
    
    if config_file.exists():
        print("📝 Sample config already exists")
        return True
    
    sample_config = {
        "app": {
            "name": "Bookmark AI Analyzer",
            "version": "1.0.0",
            "environment": "development",
            "debug": True
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": "logs/bookmark_analyzer.log",
            "max_size": 10485760,
            "backup_count": 5
        },
        "database": {
            "type": "sqlite",
            "path": "data/bookmarks.db",
            "pool_size": 10,
            "pool_timeout": 30
        },
        "processing": {
            "batch_size": 10,
            "max_workers": 4,
            "checkpoint_interval": 50,
            "checkpoint_dir": "data/checkpoints"
        },
        "analysis": {
            "default_llm_provider": "claude",
            "enable_content_analysis": True,
            "enable_categorization": True,
            "enable_tagging": True,
            "similarity_threshold": 0.7
        }
    }
    
    with open(config_file, 'w') as f:
        yaml.dump(sample_config, f, default_flow_style=False, indent=2)
    
    print("📝 Created sample configuration file")
    return True


def run_initial_tests(venv_path="venv"):
    """Run initial tests to verify setup."""
    python_cmd = f"{venv_path}/bin/python" if os.name != 'nt' else f"{venv_path}\\Scripts\\python.exe"
    
    print("🧪 Running initial tests...")
    return run_command(f"{python_cmd} -m pytest tests/unit/test_validation.py -v", 
                      "Running validation tests", check=False)


def display_next_steps():
    """Display next steps for the user."""
    print("\n" + "="*60)
    print("🎉 Setup completed successfully!")
    print("="*60)
    print("\n📋 Next steps:")
    print("   1. Activate the virtual environment:")
    if os.name != 'nt':
        print("      source venv/bin/activate")
    else:
        print("      venv\\Scripts\\activate")
    
    print("\n   2. Update your API keys in the .env file:")
    print("      nano .env")
    
    print("\n   3. Run the application:")
    print("      python scripts/run_analysis.py --help")
    
    print("\n   4. Run tests:")
    print("      pytest")
    
    print("\n   5. View the configuration:")
    print("      cat config/sample.yaml")
    
    print("\n📚 Documentation:")
    print("   - README.md: Project overview and usage")
    print("   - config/: Configuration examples")
    print("   - tests/: Test examples and fixtures")
    
    print("\n🔧 Development:")
    print("   - Run linting: black . && isort . && flake8")
    print("   - Run type checking: mypy src/")
    print("   - Generate docs: sphinx-build -b html docs/ docs/_build/")


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description="Setup Bookmark AI Analyzer")
    parser.add_argument("--dev", action="store_true", 
                       help="Install development dependencies")
    parser.add_argument("--venv", default="venv", 
                       help="Virtual environment path (default: venv)")
    parser.add_argument("--skip-tests", action="store_true",
                       help="Skip running initial tests")
    parser.add_argument("--no-git-hooks", action="store_true",
                       help="Skip setting up git hooks")
    
    args = parser.parse_args()
    
    print("🚀 Setting up Bookmark AI Analyzer...")
    print("="*50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Create virtual environment
    if not create_virtual_environment(args.venv):
        print("❌ Failed to create virtual environment")
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies(args.dev, args.venv):
        print("❌ Failed to install dependencies")
        sys.exit(1)
    
    # Create directories
    if not create_directories():
        print("❌ Failed to create directories")
        sys.exit(1)
    
    # Create environment file
    if not create_environment_file():
        print("❌ Failed to create environment file")
        sys.exit(1)
    
    # Create sample config
    if not create_sample_config():
        print("❌ Failed to create sample config")
        sys.exit(1)
    
    # Setup git hooks (if requested)
    if not args.no_git_hooks:
        setup_git_hooks()
    
    # Run initial tests (if requested)
    if not args.skip_tests:
        run_initial_tests(args.venv)
    
    # Display next steps
    display_next_steps()


if __name__ == "__main__":
    main()