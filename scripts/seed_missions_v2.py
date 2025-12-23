# scripts/seed_missions_v2.py

"""
Безопасное засеивание миссий с upsert логикой
Не удаляет существующие миссии, а обновляет их
"""

import sys
import os
# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
import logging
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from core.database import AsyncSessionLocal
from models.mission import Mission

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_missions_from_json(file_path: str) -> list:
    """Загрузить миссии из JSON файла"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('missions', [])
    except FileNotFoundError:
        logger.error(f"❌ Файл {file_path} не найден")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"❌ Ошибка парсинга JSON: {e}")
        return []


async def upsert_mission(session: AsyncSession, mission_data: dict) -> tuple:
    """
    Обновить существующую миссию или создать новую
    Использует text + difficulty как уникальный ключ
    
    Returns: (Mission, action) где action = 'created' | 'updated' | 'unchanged'
    """
    # Ищем миссию по тексту и сложности
    result = await session.execute(
        select(Mission).where(
            Mission.text == mission_data['text'],
            Mission.difficulty == mission_data['difficulty'],
            Mission.is_archived == False
        )
    )
    existing_mission = result.scalar_one_or_none()
    
    if existing_mission:
        # Проверяем изменились ли данные
        changed = False
        
        new_tags = mission_data.get('tags_list', '')
        new_points = mission_data.get('points_reward', 10)
        new_active = mission_data.get('active', True)
        
        if existing_mission.tags_list != new_tags:
            existing_mission.tags_list = new_tags
            changed = True
        
        if existing_mission.points_reward != new_points:
            existing_mission.points_reward = new_points
            changed = True
        
        if existing_mission.active != new_active:
            existing_mission.active = new_active
            changed = True
        
        if changed:
            # Увеличиваем версию при изменении
            existing_mission.version += 1
            logger.info(f"🔄 Обновление миссии ID={existing_mission.id}, v{existing_mission.version}: {mission_data['text'][:50]}...")
            return existing_mission, 'updated'
        else:
            return existing_mission, 'unchanged'
    else:
        # Создаём новую миссию
        logger.info(f"➕ Создание новой миссии: {mission_data['text'][:50]}...")
        
        new_mission = Mission(
            text=mission_data['text'],
            tags_list=mission_data.get('tags_list', ''),
            difficulty=mission_data['difficulty'],
            points_reward=mission_data.get('points_reward', 10),
            active=mission_data.get('active', True),
            version=1,
            is_archived=False
        )
        
        session.add(new_mission)
        return new_mission, 'created'


async def archive_old_missions(session: AsyncSession, current_mission_keys: set) -> int:
    """
    Архивировать миссии, которых нет в текущем JSON
    (Soft delete вместо удаления)
    
    current_mission_keys: set of (text, difficulty) tuples
    """
    result = await session.execute(
        select(Mission).where(
            Mission.is_archived == False,
            Mission.is_group_mission == False
        )
    )
    all_missions = result.scalars().all()
    
    archived_count = 0
    for mission in all_missions:
        mission_key = (mission.text, mission.difficulty)
        if mission_key not in current_mission_keys:
            logger.info(f"📦 Архивация миссии ID={mission.id}: {mission.text[:50]}...")
            mission.is_archived = True
            mission.archived_at = datetime.utcnow()
            mission.active = False
            archived_count += 1
    
    return archived_count


async def seed_missions_safe():
    """
    Безопасное засеивание миссий
    - Обновляет существующие
    - Создаёт новые
    - Архивирует удалённые из JSON
    """
    async with AsyncSessionLocal() as session:
        try:
            # Загружаем миссии из JSON
            json_path = Path(__file__).parent.parent / "data" / "missions.json"
            missions_data = load_missions_from_json(str(json_path))
            
            if not missions_data:
                logger.warning("⚠️ Нет миссий для загрузки")
                return
            
            logger.info(f"📥 Загружено {len(missions_data)} миссий из JSON")
            
            # Upsert каждой миссии
            updated_count = 0
            created_count = 0
            unchanged_count = 0
            current_keys = set()
            
            for mission_data in missions_data:
                mission, action = await upsert_mission(session, mission_data)
                current_keys.add((mission_data['text'], mission_data['difficulty']))
                
                if action == 'created':
                    created_count += 1
                elif action == 'updated':
                    updated_count += 1
                else:
                    unchanged_count += 1
            
            # Архивируем удалённые миссии
            archived_count = await archive_old_missions(session, current_keys)
            
            # Коммитим все изменения
            await session.commit()
            
            logger.info(f"✅ Засеивание завершено успешно!")
            logger.info(f"   ➕ Создано новых: {created_count}")
            logger.info(f"   🔄 Обновлено: {updated_count}")
            logger.info(f"   ⏭️  Без изменений: {unchanged_count}")
            logger.info(f"   📦 Заархивировано: {archived_count}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при засеивании: {e}", exc_info=True)
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(seed_missions_safe())