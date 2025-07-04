"""Configuration settings management."""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from functools import lru_cache

import yaml
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class LLMConfig(BaseModel):
    """LLM provider configuration."""
    
    api_key: str
    model: str
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 30
    max_retries: int = 3
    rate_limit: int = 60  # requests per minute


class GrokConfig(LLMConfig):
    """Grok-specific configuration."""
    
    model: str = "grok-beta"
    base_url: str = "https://api.x.ai/v1"


class ClaudeConfig(LLMConfig):
    """Claude-specific configuration."""
    
    model: str = "claude-3-opus-20240229"
    base_url: str = "https://api.anthropic.com"
    anthropic_version: str = "2023-06-01"


class GeminiConfig(LLMConfig):
    """Gemini-specific configuration."""
    
    model: str = "gemini-pro"
    base_url: str = "https://generativelanguage.googleapis.com"


class ProcessingConfig(BaseModel):
    """Processing configuration."""
    
    batch_size: int = 100
    max_workers: int = 4
    checkpoint_interval: int = 50
    memory_limit_mb: int = 2048
    enable_caching: bool = True
    cache_ttl: int = 3600


class ExportConfig(BaseModel):
    """Export configuration."""
    
    formats: list[str] = ["json", "anki", "notion", "obsidian"]
    output_dir: Path = Path("data/processed")
    compress: bool = True
    include_metadata: bool = True


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = "INFO"
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}"
    rotation: str = "10 MB"
    retention: str = "30 days"
    backtrace: bool = True
    diagnose: bool = True


class Settings(BaseSettings):
    """Main application settings."""
    
    # Application
    app_name: str = "bookmark-ai-analyzer"
    version: str = "0.1.0"
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Paths
    project_root: Path = Path(__file__).parent.parent.parent
    data_dir: Path = Field(default_factory=lambda: Path("data"))
    config_dir: Path = Field(default_factory=lambda: Path("config"))
    checkpoint_dir: Path = Field(default_factory=lambda: Path("checkpoints"))
    
    # LLM Providers
    grok: Optional[GrokConfig] = None
    claude: Optional[ClaudeConfig] = None
    gemini: Optional[GeminiConfig] = None
    default_llm: str = "claude"
    
    # Processing
    processing: ProcessingConfig = ProcessingConfig()
    
    # Export
    export: ExportConfig = ExportConfig()
    
    # Logging
    logging: LoggingConfig = LoggingConfig()
    
    # Database
    database_url: str = Field(
        default="sqlite:///data/bookmarks.db",
        env="DATABASE_URL"
    )
    
    # Redis
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator("data_dir", "config_dir", "checkpoint_dir", pre=True)
    def resolve_paths(cls, v, values):
        """Resolve relative paths to absolute."""
        if isinstance(v, str):
            v = Path(v)
        if not v.is_absolute():
            project_root = values.get("project_root", Path.cwd())
            return project_root / v
        return v
    
    @classmethod
    def from_yaml(cls, config_path: Path) -> "Settings":
        """Load settings from YAML file."""
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
        
        # Load LLM configs from separate file if specified
        llm_config_path = config_path.parent / "llm_configs.yaml"
        if llm_config_path.exists():
            with open(llm_config_path, "r") as f:
                llm_data = yaml.safe_load(f)
                config_data.update(llm_data)
        
        # Override with environment variables
        env_overrides = {}
        for key in ["GROK_API_KEY", "CLAUDE_API_KEY", "GEMINI_API_KEY"]:
            if value := os.getenv(key):
                provider = key.lower().replace("_api_key", "")
                if provider not in config_data:
                    config_data[provider] = {}
                config_data[provider]["api_key"] = value
        
        return cls(**config_data)
    
    def validate_llm_config(self) -> None:
        """Validate that at least one LLM provider is configured."""
        providers = [self.grok, self.claude, self.gemini]
        if not any(providers):
            raise ValueError("At least one LLM provider must be configured")
        
        # Check default provider
        available_providers = []
        if self.grok:
            available_providers.append("grok")
        if self.claude:
            available_providers.append("claude")
        if self.gemini:
            available_providers.append("gemini")
        
        if self.default_llm not in available_providers:
            raise ValueError(
                f"Default LLM '{self.default_llm}' is not configured. "
                f"Available: {available_providers}"
            )


@lru_cache()
def get_settings(config_path: Optional[Path] = None) -> Settings:
    """Get cached settings instance."""
    if config_path:
        return Settings.from_yaml(config_path)
    
    # Try to load from environment-specific config
    env = os.getenv("ENVIRONMENT", "development")
    config_file = Path(f"config/{env}.yaml")
    
    if config_file.exists():
        return Settings.from_yaml(config_file)
    
    # Fall back to default settings
    return Settings()


def create_config_template(output_path: Path) -> None:
    """Create a configuration template file."""
    template = {
        "environment": "development",
        "debug": True,
        "grok": {
            "api_key": "your-grok-api-key",
            "model": "grok-beta",
            "max_tokens": 4096,
            "temperature": 0.7
        },
        "claude": {
            "api_key": "your-claude-api-key", 
            "model": "claude-3-opus-20240229",
            "max_tokens": 4096,
            "temperature": 0.7
        },
        "gemini": {
            "api_key": "your-gemini-api-key",
            "model": "gemini-pro",
            "max_tokens": 4096,
            "temperature": 0.7
        },
        "default_llm": "claude",
        "processing": {
            "batch_size": 100,
            "max_workers": 4,
            "checkpoint_interval": 50,
            "memory_limit_mb": 2048,
            "enable_caching": True,
            "cache_ttl": 3600
        },
        "export": {
            "formats": ["json", "anki", "notion", "obsidian"],
            "output_dir": "data/processed",
            "compress": True,
            "include_metadata": True
        },
        "logging": {
            "level": "INFO",
            "rotation": "10 MB",
            "retention": "30 days",
            "backtrace": True,
            "diagnose": True
        }
    }
    
    with open(output_path, "w") as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False)
    
    print(f"Configuration template created at: {output_path}")