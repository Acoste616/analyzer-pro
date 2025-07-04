#!/usr/bin/env python3
"""Setup script for Bookmark AI Analyzer."""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.settings import create_config_template


def setup_project():
    """Set up the project structure and configuration."""
    print("Setting up Bookmark AI Analyzer...")
    
    # Create necessary directories
    directories = [
        "data/raw",
        "data/processed", 
        "data/knowledge_base",
        "logs",
        "checkpoints",
        "config",
    ]
    
    for dir_path in directories:
        path = project_root / dir_path
        path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {dir_path}")
    
    # Create config templates
    config_files = ["development.yaml", "production.yaml", "test.yaml"]
    
    for config_file in config_files:
        config_path = project_root / "config" / config_file
        if not config_path.exists():
            create_config_template(config_path)
            print(f"✓ Created config template: {config_file}")
    
    # Create .env template
    env_template = """# Environment variables for Bookmark AI Analyzer

# Environment
ENVIRONMENT=development

# API Keys
GROK_API_KEY=your-grok-api-key-here
CLAUDE_API_KEY=your-claude-api-key-here
GEMINI_API_KEY=your-gemini-api-key-here

# Database
DATABASE_URL=sqlite:///data/bookmarks.db

# Redis (optional)
# REDIS_URL=redis://localhost:6379/0

# Debug
DEBUG=true
"""
    
    env_path = project_root / ".env.template"
    with open(env_path, "w") as f:
        f.write(env_template)
    print("✓ Created .env.template")
    
    print("\n✅ Setup complete!")
    print("\nNext steps:")
    print("1. Copy .env.template to .env and add your API keys")
    print("2. Review and adjust config files in config/")
    print("3. Install dependencies: pip install -r requirements.txt")
    print("4. Run tests: pytest")
    print("5. Start processing: python -m bookmark_analyzer process --input your_bookmarks.csv")


if __name__ == "__main__":
    setup_project()