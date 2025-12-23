# migrations/add_group_columns.py

"""
Добавление колонок emoji и is_published в таблицу mission_groups
"""

import asyncio
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import async_session_maker
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_group_columns():
    """Добавить новые колонки в таблицу mission_groups"""
    
    async with async_session_maker() as session:
        try:
            # Проверяем существование колонки emoji
            check_emoji = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='mission_groups' AND column_name='emoji'
            """))
            
            if not check_emoji.scalar():
                logger.info("Добавляем колонку emoji...")
                await session.execute(text("""
                    ALTER TABLE mission_groups 
                    ADD COLUMN emoji VARCHAR(10) DEFAULT '🎯'
                """))
                logger.info("✅ Колонка emoji добавлена")
            else:
                logger.info("✅ Колонка emoji уже существует")
            
            # Проверяем существование колонки is_published
            check_published = await session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='mission_groups' AND column_name='is_published'
            """))
            
            if not check_published.scalar():
                logger.info("Добавляем колонку is_published...")
                await session.execute(text("""
                    ALTER TABLE mission_groups 
                    ADD COLUMN is_published BOOLEAN DEFAULT false
                """))
                logger.info("✅ Колонка is_published добавлена")
            else:
                logger.info("✅ Колонка is_published уже существует")
            
            # Обновляем старые записи
            logger.info("Обновляем существующие записи...")
            
            # Устанавливаем emoji из icon (если есть)
            await session.execute(text("""
                UPDATE mission_groups 
                SET emoji = COALESCE(icon, '🎯') 
                WHERE emoji IS NULL
            """))
            
            # Публикуем активные группы
            await session.execute(text("""
                UPDATE mission_groups 
                SET is_published = true 
                WHERE is_active = true AND is_published IS NULL
            """))
            
            await session.commit()
            logger.info("✅ Миграция завершена успешно!")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при миграции: {e}", exc_info=True)
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(add_group_columns())
