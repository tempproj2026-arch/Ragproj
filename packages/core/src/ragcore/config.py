import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # General
    data_root: Path
    environment: str = "dev"
    
    # Database
    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str
    db_user: str
    db_password: str
    mcp_ro_user: str
    mcp_ro_password: str
    
    # LM Studio & Models
    lm_studio_url: str = "http://localhost:1234/v1"
    vision_model_name: str
    embedding_device: str = "cpu"
    reranker_device: str = "cpu"
    
    # Offline Model Paths
    bge_m3_path: Path
    reranker_path: Path
    docling_models_path: Path
    siglip_path: Path

    model_config = SettingsConfigDict(
        # Look for .env in the project root (up 4 levels from this file usually, or just CWD)
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_db_url(self, role: str = "ingest") -> str:
        if role == "mcp_ro":
            return f"postgresql://{self.mcp_ro_user}:{self.mcp_ro_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

settings = Settings()
