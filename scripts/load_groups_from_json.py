
# scripts/load_groups_from_json.py

"""
Загрузить группы миссий из JSON-файла
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import async_session_maker
from models.mission_group import MissionGroup, GroupType, AccessType
from models.mission import Mission
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def load_groups_from_json():
    """Загрузить группы из JSON"""
    
    # Путь к JSON-файлу
    json_path = Path(__file__).parent.parent / "data" / "mission_groups.json"
    
    if not json_path.exists():
        logger.error(f"❌ Файл не найден: {json_path}")
        return
    
    # Читаем JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    async with async_session_maker() as session:
        
        for group_data in data['groups']:
            # Создаём группу
            group = MissionGroup(
                name=group_data['name'],
                description=group_data['description'],
                emoji=group_data['emoji'],
                group_type=GroupType(group_data['group_type']),
                access_type=AccessType(group_data['access_type']),
                required_level=group_data['required_level'],
                is_active=group_data['is_active'],
                is_published=group_data['is_published'],
                order_index=group_data['order_index'],
                completion_bonus=group_data['completion_bonus']
            )
            
            session.add(group)
            await session.flush()  # Получаем ID группы
            
            # Создаём миссии для группы
            missions_count = 0
            for mission_data in group_data['missions']:
                mission = Mission(
                    text=mission_data['text'],
                    difficulty=mission_data['difficulty'],
                    points_reward=mission_data['points_reward'],
                    tags=mission_data['tags'],
                    active=True,
                    group_id=group.id,
                    is_group_mission=True,
                    sequence_order=mission_data.get('sequence_order')  # Для sequential
                )
                session.add(mission)
                missions_count += 1
            
            logger.info(f"✅ Создана группа: {group.name} ({missions_count} миссий)")
        
        await session.commit()
        
        logger.info("\n🎉 Все группы успешно загружены из JSON!")


async def main():
    try:
        await load_groups_from_json()
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
