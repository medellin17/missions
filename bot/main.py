# bot/main.py
"""
Главная точка входа бота. 
Инициализация, регистрация handlers, запуск polling. 
"""

import asyncio
import logging
from typing import NoReturn

from aiogram import Bot, Dispatcher
from aiogram. fsm. storage.redis import RedisStorage
from aiogram.fsm.strategy import FSMStrategy
from redis.asyncio import Redis

from core.config import settings
from core. database import init_db, dispose_db, test_connection
from core.scheduler import NotificationScheduler
from core.middleware import DatabaseSessionMiddleware

# ✅ Импортируем handlers модули (они регистрируют свои routers)
from handlers import (
    start,
    mission,
    pair,
    notification,
    theme_week,
    mission_groups,
    mission_groups_user,  # ✅ ДОБАВИЛ (был в __all__, но не импортирован)
)
from handlers.admin import analytics as admin_analytics, missions as admin_missions, users as admin_users

# Настройка логирования
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def setup_storage() -> tuple[RedisStorage, Redis]:
    """Инициализация Redis хранилища для FSM."""
    logger.info(f"Connecting to Redis:  {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    
    redis_client = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD,
        decode_responses=True,
    )
    
    # Тест соединения
    try:  
        await redis_client.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed:  {e}")
        raise
    
    storage = RedisStorage(
        redis=redis_client,
        state_ttl=86400,
        data_ttl=86400,
        key_builder=None,
        fsm_strategy=FSMStrategy. CHAT_MEMBER_ID,
    )
    
    return storage, redis_client


async def setup_dispatcher(bot: Bot, storage: RedisStorage) -> Dispatcher:
    """Конфигурирование dispatcher:  middleware, handlers, роутеры."""
    dp = Dispatcher(storage=storage)
    
    # ========== MIDDLEWARE ==========
    dp.message.middleware(DatabaseSessionMiddleware())
    dp.callback_query.middleware(DatabaseSessionMiddleware())
    dp.errors.middleware(DatabaseSessionMiddleware())
    
    # ========== ROUTER REGISTRATION ==========
    # Порядок важен:  общие handlers → специфичные
    dp.include_router(start.router)
    dp.include_router(mission.router)
    dp.include_router(mission_groups.router)
    dp.include_router(mission_groups_user.router)  # ✅ ДОБАВИЛ
    dp.include_router(pair.router)
    dp.include_router(notification.router)
    dp.include_router(theme_week.router)
    
    # Admin handlers
    dp.include_router(admin_analytics.router)
    dp.include_router(admin_missions.router)
    dp.include_router(admin_users.router)
    
    logger.info("✅ All routers registered")
    
    return dp


async def main() -> NoReturn:
    """Главная функция запуска бота."""
    logger.info(f"🤖 Starting Micro-Mission Bot (env={settings.ENVIRONMENT})")
    
    # ========== DATABASE ==========
    logger.info("Initializing database...")
    await test_connection()
    await init_db()
    
    # ========== BOT & DISPATCHER ==========
    bot = Bot(token=settings.BOT_TOKEN)
    storage, redis_client = await setup_storage()
    dp = await setup_dispatcher(bot, storage)
    
    # ========== SCHEDULER ==========
    scheduler = NotificationScheduler()
    
    # ========== RUN ==========
    try:
        logger.info("🚀 Bot polling started")
        await asyncio.gather(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
            scheduler.start_scheduler(),
        )
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt")
    finally:
        logger.info("Shutting down...")
        await dp.storage.close()
        await redis_client.close()
        await dispose_db()
        await bot.session.close()
        logger.info("✅ Bot shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}", exc_info=True)
        raise