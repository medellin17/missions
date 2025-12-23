#/core/middleware.py
"""
Middleware для инъекции AsyncSession в хэндлеры Aiogram v3.
Любой хэндлер, принимающий параметр `db_session`, получит активную сессию БД.
"""
from typing import Any, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from core.database import AsyncSessionLocal


class DatabaseSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Any],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with AsyncSessionLocal() as session:
            # Передаем сессию в контекст хэндлера
            data["db_session"] = session
            return await handler(event, data)