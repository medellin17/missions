/core/config.py
"""
Конфигурация приложения через Pydantic.
Все переменные берутся из . env файла.
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
from pathlib import Path


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # ========== BOT ==========
    BOT_TOKEN: str  # Telegram bot token (обязательно)
    ADMIN_IDS: List[int] = []  # List of admin user IDs
    
    # ========== DATABASE ==========
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_USER: str = "postgres"
    DATABASE_PASSWORD: str  # Обязательно из . env
    DATABASE_NAME: str = "micro_mission"
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct async PostgreSQL connection string"""
        return (
            f"postgresql+asyncpg://"
            f"{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@"
            f"{self.DATABASE_HOST}:{self.DATABASE_PORT}/"
            f"{self.DATABASE_NAME}"
        )
    
    # ========== REDIS ==========
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    @property
    def REDIS_URL(self) -> str:
        """Construct Redis connection string"""
        if self.REDIS_PASSWORD: 
            return (
                f"redis://:{self.REDIS_PASSWORD}@"
                f"{self. REDIS_HOST}:{self. REDIS_PORT}/{self.REDIS_DB}"
            )
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # ========== MISSION SETTINGS ==========
    MAX_CHARGES_PER_DAY: int = 3
    CHARGE_RESET_TIME: str = "00:00"  # HH:MM format
    DEFAULT_MISSION_POINTS: int = 10
    
    # ========== PAIR SETTINGS ==========
    MAX_PAIR_USERS: int = 2
    PAIR_TIMEOUT_MINUTES: int = 30
    
    # ========== LOGGING ==========
    LOG_LEVEL: str = "INFO"
    
    # ========== ENVIRONMENT ==========
    ENVIRONMENT: str = "development"  # development | production
    DEBUG: bool = False
    
    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
        # Для документации
        json_schema_extra = {
            "example": {
                "BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
                "DATABASE_PASSWORD": "secure_password_here",
                "ADMIN_IDS": [123456789, 987654321],
            }
        }


# ✅ Глобальный экземпляр конфигурации
settings = Settings()