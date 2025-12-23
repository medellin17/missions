# bot/main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from core.config import settings
from core.scheduler import NotificationScheduler
from handlers import mission, pair, notification, theme_week, admin_analytics, start, admin_missions
from core.middleware import DatabaseSessionMiddleware # <-- Импортируем middleware
from handlers import mission_groups


async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=settings.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Регистрируем middleware для сессии БД
    dp.message.middleware(DatabaseSessionMiddleware())
    dp.callback_query.middleware(DatabaseSessionMiddleware()) # <-- Добавим и для callback_query, если они используют сессию

    # Подключаем роутеры
    dp.include_router(start.router)
    dp.include_router(mission.router)
    dp.include_router(pair.router)
    dp.include_router(notification.router)
    dp.include_router(theme_week.router)
    dp.include_router(admin_analytics.router)
    dp.include_router(mission_groups.router)

    # Создаем и запускаем планировщик уведомлений
    scheduler = NotificationScheduler()

    print("Bot is starting...")

    # Запускаем бота и планировщик параллельно
    await asyncio.gather(
        dp.start_polling(bot),
        scheduler.start_scheduler()
    )


if __name__ == "__main__":
    asyncio.run(main())