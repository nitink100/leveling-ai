import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# 1. Get the directory where THIS file (config.py) is located
# 2. Go up 2 levels to reach the /backend folder
# config.py is in backend/app/core/
# .parent.parent is backend/app
# .parent.parent.parent is backend/
# .env file is located in backend/
PROJECT_ROOT = Path(__file__).parent.parent.parent

class Settings(BaseSettings):
    app_name: str = "LevelingAI"
    env: str = "local"
    DATABASE_URL: str

    model_config = SettingsConfigDict(
        # This creates an absolute path to your .env file
        env_file=os.path.join(PROJECT_ROOT, ".env"), 
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

settings = Settings()