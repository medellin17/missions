#/core/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from core.config import settings
import logging


logger = logging.getLogger(__name__)

# Создаем асинхронный движок
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Установите True для логирования SQL-запросов
    pool_pre_ping=True
)

# Создаем фабрику сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False
)


async def get_db_session():
    """Генератор сессии базы данных для Dependency Injection"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Инициализация базы данных - создание таблиц"""
    # Импортируем Base внутри функции, чтобы избежать циклических импортов
    from models import Base
    async with engine.begin() as conn:
        # Создаем все таблицы
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")


async def test_connection():
    """Тест подключения к базе данных"""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False