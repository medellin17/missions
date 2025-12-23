#/core/database.py
"""
Инициализация базы данных и сессий. 
Использует ЕДИНСТВЕННЫЙ Base из models/base.py
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy. ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy import text

from core.config import settings
from models.base import Base  # ✅ Импортируем ЕДИНСТВЕННЫЙ Base

logger = logging.getLogger(__name__)

# ========== ENGINE ==========
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # Логирование SQL только в DEBUG
    pool_size=20,  # Размер пула соединений
    max_overflow=0,  # Без дополнительных соединений сверх pool_size
    pool_pre_ping=True,  # Проверка соединения перед использованием
)

# ========== SESSION FACTORY ==========
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # ✅ Важно для async работы
)


# ========== DEPENDENCY INJECTION ==========
async def get_db_session() -> AsyncGenerator[AsyncSession, None]: 
    """
    Генератор сессии БД для Dependency Injection. 
    Использование: 
        async def handler(message: Message, db_session: AsyncSession):
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ========== INITIALIZATION ==========
async def init_db() -> None:
    """
    Инициализация БД:  создание всех таблиц.
    ВАЖНО: Вызывать ДО запуска бота!
    """
    try:
        logger.info("Initializing database...")
        async with engine.begin() as conn:
            # ✅ Создаем таблицы из ЕДИНСТВЕННОГО Base
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}", exc_info=True)
        raise


async def test_connection() -> bool:
    """Проверка подключения к БД"""
    try:
        async with engine. begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection successful")
        return True
    except Exception as e:
        logger. error(f"❌ Database connection failed: {e}")
        return False


async def dispose_db() -> None:
    """Закрытие всех соединений (при завершении приложения)"""
    await engine.dispose()
    logger.info("Database connections disposed")