#/core/middleware.py
from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from core.database import get_db_session


class DatabaseSessionMiddleware(BaseMiddleware):
    """
    Middleware для автоматического внедрения AsyncSession в хендлеры.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        # Создаем асинхронную сессию
        async for session in get_db_session():
            # Добавляем сессию в словарь data, который передается в хендлер
            data["db_session"] = session
            # Вызываем следующий обработчик (handler)
            result = await handler(event, data)
            # Сессия автоматически закроется при выходе из генератора
            return result
