from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "NoorLink Automation"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    
    supabase_url: str
    supabase_key: str
    supabase_service_key: Optional[str] = None
    
    stripe_secret_key: str
    stripe_publishable_key: str
    stripe_webhook_secret: str
    
    resend_api_key: str
    resend_from_email: str = "noreply@noorlink.com"
    
    secret_key: str = "change-this-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
