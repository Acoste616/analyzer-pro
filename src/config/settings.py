import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class DatabaseConfig:
    type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    path: Optional[str] = None
    pool_size: int = 10
    pool_timeout: int = 30


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "logs/bookmark_analyzer.log"
    max_size: int = 10485760
    backup_count: int = 5


@dataclass
class ProcessingConfig:
    batch_size: int = 10
    max_workers: int = 4
    checkpoint_interval: int = 50
    checkpoint_dir: str = "data/checkpoints"


@dataclass
class RateLimitConfig:
    requests_per_minute: int = 60
    tokens_per_minute: Optional[int] = None


@dataclass
class ExtractorConfig:
    base_url: str
    timeout: int = 30
    retry_attempts: int = 3
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)


@dataclass
class AnalysisConfig:
    default_llm_provider: str = "claude"
    enable_content_analysis: bool = True
    enable_categorization: bool = True
    enable_tagging: bool = True
    similarity_threshold: float = 0.7


@dataclass
class KnowledgeBaseConfig:
    output_dir: str = "data/knowledge_base"
    formats: list = field(default_factory=lambda: ["markdown", "json", "csv"])
    include_metadata: bool = True


@dataclass
class MonitoringConfig:
    enable_metrics: bool = True
    metrics_port: int = 8080
    health_check_interval: int = 300


@dataclass
class AppConfig:
    name: str = "Bookmark AI Analyzer"
    version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False


@dataclass
class Settings:
    app: AppConfig = field(default_factory=AppConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    extractors: Dict[str, ExtractorConfig] = field(default_factory=dict)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    knowledge_base: KnowledgeBaseConfig = field(default_factory=KnowledgeBaseConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)


class SettingsManager:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.settings = self._load_settings()
        self.llm_configs = self._load_llm_configs()
    
    def _get_default_config_path(self) -> str:
        env = os.getenv("ENVIRONMENT", "development")
        return f"config/{env}.yaml"
    
    def _load_settings(self) -> Settings:
        try:
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            return self._dict_to_settings(config_data)
        except FileNotFoundError:
            print(f"Config file {self.config_path} not found. Using default settings.")
            return Settings()
        except yaml.YAMLError as e:
            print(f"Error parsing config file: {e}")
            return Settings()
    
    def _load_llm_configs(self) -> Dict[str, Any]:
        llm_config_path = "src/config/llm_configs.yaml"
        try:
            with open(llm_config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"LLM config file {llm_config_path} not found.")
            return {}
        except yaml.YAMLError as e:
            print(f"Error parsing LLM config file: {e}")
            return {}
    
    def _dict_to_settings(self, config_data: Dict[str, Any]) -> Settings:
        app_config = AppConfig(**config_data.get("app", {}))
        
        db_data = config_data.get("database", {})
        database_config = DatabaseConfig(**db_data)
        
        logging_config = LoggingConfig(**config_data.get("logging", {}))
        processing_config = ProcessingConfig(**config_data.get("processing", {}))
        
        extractors_data = config_data.get("extractors", {})
        extractors = {}
        for name, extractor_data in extractors_data.items():
            rate_limit_data = extractor_data.pop("rate_limit", {})
            rate_limit = RateLimitConfig(**rate_limit_data)
            extractors[name] = ExtractorConfig(**extractor_data, rate_limit=rate_limit)
        
        analysis_config = AnalysisConfig(**config_data.get("analysis", {}))
        knowledge_base_config = KnowledgeBaseConfig(**config_data.get("knowledge_base", {}))
        monitoring_config = MonitoringConfig(**config_data.get("monitoring", {}))
        
        return Settings(
            app=app_config,
            database=database_config,
            logging=logging_config,
            processing=processing_config,
            extractors=extractors,
            analysis=analysis_config,
            knowledge_base=knowledge_base_config,
            monitoring=monitoring_config
        )
    
    def get_llm_config(self, provider: str) -> Optional[Dict[str, Any]]:
        return self.llm_configs.get("llm_providers", {}).get(provider)
    
    def get_analysis_prompt(self, prompt_type: str) -> Optional[Dict[str, str]]:
        return self.llm_configs.get("analysis_prompts", {}).get(prompt_type)
    
    def reload_settings(self):
        self.settings = self._load_settings()
        self.llm_configs = self._load_llm_configs()


settings_manager = SettingsManager()