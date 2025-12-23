# scripts/seed_missions.py
import asyncio
import sys
import os
import json
from pathlib import Path

# Добавляем корневую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from core.config import settings
from models.mission import Mission
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def load_missions_from_json(json_path: str = "data/missions.json") -> list:
    """Загрузить миссии из JSON файла"""
    try:
        file_path = Path(json_path)
        if not file_path.exists():
            logger.error(f"❌ Файл {json_path} не найден!")
            return []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            missions = data.get('missions', [])
            logger.info(f"✅ Загружено {len(missions)} миссий из {json_path}")
            return missions
    except json.JSONDecodeError as e:
        logger.error(f"❌ Ошибка парсинга JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Ошибка при чтении файла: {e}")
        return []


async def seed_missions(force_reload: bool = False):
    """
    Засеять базу данных миссиями из JSON
    
    Args:
        force_reload: Если True, удалит все существующие миссии и загрузит заново
    """
    
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    
    # Загружаем миссии из JSON
    missions_data = await load_missions_from_json()
    
    if not missions_data:
        logger.error("❌ Нет миссий для загрузки")
        return
    
    async with AsyncSessionLocal() as session:
        try:
            # Проверяем, есть ли уже миссии в БД
            result = await session.execute(select(Mission))
            existing_missions = result.scalars().all()
            
            if existing_missions and not force_reload:
                logger.info(f"📊 В базе уже есть {len(existing_missions)} миссий. Пропускаем засеивание.")
                logger.info("💡 Используйте force_reload=True для перезагрузки миссий")
                return
            
            # Если force_reload, удаляем старые миссии
            if force_reload and existing_missions:
                logger.info(f"🗑️  Удаление {len(existing_missions)} существующих миссий...")
                for mission in existing_missions:
                    await session.delete(mission)
                await session.commit()
                logger.info("✅ Старые миссии удалены")
            
            # Добавляем миссии из JSON
            added_count = 0
            for data in missions_data:
                mission = Mission(
                    text=data["text"],
                    difficulty=data.get("difficulty", "базовая"),
                    points_reward=data.get("points_reward", 10),
                    active=data.get("active", True)
                )
                mission.tags = data.get("tags", [])  # Используем property setter
                session.add(mission)
                added_count += 1
            
            await session.commit()
            logger.info(f"✅ Успешно добавлено {added_count} миссий в базу данных!")
            
            # Статистика по категориям
            basic_count = sum(1 for m in missions_data if m.get('difficulty') == 'базовая')
            elite_count = sum(1 for m in missions_data if m.get('difficulty') == 'элитная')
            logger.info(f"📊 Статистика: {basic_count} базовых, {elite_count} элитных миссий")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при засеивании миссий: {e}")
            await session.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    # Проверяем аргументы командной строки
    force = "--force" in sys.argv or "-f" in sys.argv
    
    if force:
        logger.warning("⚠️  Запущена принудительная перезагрузка миссий!")
    
    asyncio.run(seed_missions(force_reload=force))