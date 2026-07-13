import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "smart_uploader"
    
    # We store files relative to the workspace root or can specify an absolute path.
    # Default is the 'storage' directory inside the engine directory.
    STORAGE_ROOT: str = os.path.abspath(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")
    )
    
    # Secret key for security/signing
    SECRET_KEY: str = "supersecret_smart_uploader_key_2026"
    
    # URL used for file shortlink generator
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
