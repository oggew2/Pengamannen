from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
import yaml
from dotenv import load_dotenv

# Load .env file
load_dotenv(Path(__file__).parent.parent / ".env")

class Settings(BaseSettings):
    eodhd_api_key: str = ""
    database_url: str = "sqlite:///./app.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "info"
    data_sync_enabled: bool = True
    data_sync_hour: int = 18
    
    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache
def get_settings() -> Settings:
    return Settings()

@lru_cache
def load_strategies_config() -> dict:
    path = Path(__file__).parent / "strategies.yaml"
    with open(path) as f:
        return yaml.safe_load(f)
