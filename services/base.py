#/services/base.py

"""
Базовый класс для всех сервисов. 
Инкапсулирует логику работы с БД. 
"""

from typing import TypeVar, Generic
import logging

from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseService(Generic[T]):
    """
    Базовый сервис для работы с моделями.
    Содержит повторяющуюся логику.
    """
    
    def __init__(self, db_session: AsyncSession):
        """
        Args:
            db_session:  Асинхронная сессия SQLAlchemy
        """
        self.db_session = db_session
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def commit(self) -> None:
        """Сохранить изменения в БД"""
        try:
            await self.db_session.commit()
        except Exception as e: 
            self.logger.error(f"Commit failed: {e}", exc_info=True)
            await self.db_session.rollback()
            raise
    
    async def flush(self) -> None:
        """Flush изменения без commit (для единовременных операций)"""
        try:
            await self.db_session. flush()
        except Exception as e:
            self.logger.error(f"Flush failed: {e}", exc_info=True)
            raise
    
    async def rollback(self) -> None:
        """Откатить все изменения"""
        await self.db_session.rollback()