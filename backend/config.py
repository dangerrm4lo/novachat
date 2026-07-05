# config.py
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    APP_NAME: str = "NovaChat"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # SQLite (файл будет создан автоматически)
    DATABASE_URL: str = "sqlite:///./messenger.db"
    
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-change-me")
    
settings = Settings()