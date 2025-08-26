from pydantic_settings import BaseSettings
from pydantic import validator
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # Application settings
    app_name: str = "LawChronicle API"
    app_version: str = "1.0.0"
    debug: bool = True
    
    # Database settings
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "Statutes"
    
    # Security settings
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Azure OpenAI settings
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment_name: Optional[str] = None
    
    # CORS settings
    allowed_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # Batch processing settings
    max_batch_size: int = 1000
    batch_timeout: int = 300  # seconds

    class Config:
        env_file = ".env"

    @validator('debug', pre=True)
    def parse_debug(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            val = v.strip().lower()
            if val in ('1', 'true', 'yes', 'on'):
                return True
            if val in ('0', 'false', 'no', 'off'):
                return False
        return bool(v)


settings = Settings()
