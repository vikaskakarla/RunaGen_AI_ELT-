"""
Application Settings
Centralized configuration loaded from environment variables
"""
import os
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import Optional

load_dotenv()

@dataclass
class Settings:
    """Application settings from environment"""
    # API Keys
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    
    # MongoDB
    mongo_uri: str = ""
    mongo_db: str = "runagen_ml_warehouse"
    
    # BigQuery
    gcp_project_id: str = ""
    google_credentials: str = ""
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Pipeline
    pipeline_mode: str = "development"
    data_staleness_hours: float = 2.0  # Consider data stale after this many hours
    auto_pipeline_on_startup: bool = True
    
    # Model paths
    model_path: str = "./models"

_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get or create settings singleton"""
    global _settings
    if _settings is None:
        _settings = Settings(
            adzuna_app_id=os.getenv('ADZUNA_APP_ID', ''),
            adzuna_app_key=os.getenv('ADZUNA_APP_KEY', ''),
            mongo_uri=os.getenv('MONGO_URI', ''),
            mongo_db=os.getenv('MONGO_DB', 'runagen_ml_warehouse'),
            gcp_project_id=os.getenv('GCP_PROJECT_ID', ''),
            google_credentials=os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''),
            api_host=os.getenv('API_HOST', '0.0.0.0'),
            api_port=int(os.getenv('API_PORT', '8000')),
            pipeline_mode=os.getenv('PIPELINE_MODE', 'development'),
            data_staleness_hours=float(os.getenv('DATA_STALENESS_HOURS', '2.0')),
            auto_pipeline_on_startup=os.getenv('AUTO_PIPELINE_ON_STARTUP', 'true').lower() == 'true',
            model_path=os.getenv('MODEL_PATH', './models'),
        )
    return _settings
