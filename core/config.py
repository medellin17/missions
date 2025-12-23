#/core/config.py
from pydantic_settings import BaseSettings
from typing import Optional, List
from datetime import timedelta


class Settings(BaseSettings):
    # Bot settings
    BOT_TOKEN: str
    ADMIN_IDS: List[int] = []
    
    # Database settings
    DATABASE_URL: str = "postgresql+asyncpg://micro_mission:password@db:5432/micro_mission"
    REDIS_URL: str = "redis://redis:6379"
    
    # Mission settings
    MAX_CHARGES_PER_DAY: int = 3
    CHARGE_RESET_TIME: str = "00:00"  # HH:MM format
    DEFAULT_MISSION_POINTS: int = 10
    
    # Pair settings
    MAX_PAIR_USERS: int = 2
    PAIR_TIMEOUT_MINUTES: int = 30
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()