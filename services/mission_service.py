# services/mission_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Optional, Dict
import random
from datetime import datetime, timedelta
import logging

from models.mission import Mission
from models.user import User
from models.pair_mission import PairMission


logger = logging.getLogger(__name__)


class MissionService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_random_mission(self, difficulty: str = "базовая", group_id: Optional[int] = None) -> Optional[Mission]:
        """Получить случайную миссию по сложности и группе"""
        try:
            conditions = [
                Mission.difficulty == difficulty,
                Mission.active == True
            ]
            
            # Если указана группа, фильтруем по ней
            if group_id:
                conditions.append(Mission.group_id == group_id)
            
            result = await self.db_session.execute(
                select(Mission).where(and_(*conditions))
            )
            missions = result.scalars().all()
            
            if not missions:
                logger.warning(f"No missions found for difficulty: {difficulty}, group_id: {group_id}")
                return None
            
            selected_mission = random.choice(missions)
            logger.info(f"Selected mission {selected_mission.id} with difficulty {difficulty}")
            return selected_mission
            
        except Exception as e:
            logger.error(f"Error getting random mission: {e}")
            return None

    async def get_available_missions(self, user: User) -> List[Mission]:
        """Получить доступные миссии с учетом уровня пользователя"""
        query = select(Mission).where(
            and_(
                Mission.active == True,
                or_(
                    Mission.difficulty == "базовая",
                    and_(Mission.difficulty == "элитная", user.level >= 3)
                )
            )
        )
        result = await self.db_session.execute(query)
        missions = result.scalars().all()
        return missions

    async def get_pair_missions(self) -> List[str]:
        """Получить список парных миссий"""
        pair_missions = [
            "Сфотографируйте свой чай/кофе и обменяйтесь с партнёром",
            "Напишите друг другу короткое доброжелательное сообщение",
            "Сфотографируйте что-то красивое по пути домой и поделитесь",
            "Сделайте по 5 приседаний и отметьте выполнение",
            "Назовите 3 вещи, за которые благодарны сегодня",
            "Сфотографируйте своё настроение (лицо, позу, жест)",
            "Напишите друг другу комплимент на тему 'Ты молодец, потому что...'",
            "Сфотографируйте любимую книгу/фильм и расскажите почему",
            "Сделайте глубокий вдох и отметьте выполнение",
            "Напишите слово, которое характеризует ваш сегодняшний день"
        ]
        return pair_missions

    async def get_mission_by_weighted_random(self, user: User) -> Optional[Mission]:
        """Выбрать миссию с учетом предпочтений пользователя (weighted random)"""
        missions = await self.get_available_missions(user)
        if not missions:
            return None

        if not user.preferences:
            return random.choice(missions)

        weighted_missions = []
        for mission in missions:
            weight = 1
            for tag in mission.tags:
                weight += user.preferences.get(tag, 0)
            weighted_missions.append((mission, max(weight, 1)))

        missions_list, weights = zip(*weighted_missions)
        try:
            selected_mission = random.choices(missions_list, weights=weights)[0]
            return selected_mission
        except (IndexError, ValueError):
            return random.choice(missions) if missions else None

    async def get_mission_by_id(self, mission_id: int) -> Optional[Mission]:
        """Получить миссию по ID"""
        result = await self.db_session.execute(
            select(Mission).where(Mission.id == mission_id)
        )
        return result.scalar_one_or_none()

    async def get_all_missions(self, difficulty: Optional[str] = None, active_only: bool = True) -> List[Mission]:
        """Получить все миссии с фильтрацией"""
        query = select(Mission)
        
        conditions = []
        if active_only:
            conditions.append(Mission.active == True)
        if difficulty:
            conditions.append(Mission.difficulty == difficulty)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return result.scalars().all()

    async def create_pair_mission(self, pair_id: int) -> Optional[PairMission]:
        """Создать парную миссию"""
        pair_missions = await self.get_pair_missions()
        if not pair_missions:
            return None

        mission_text = random.choice(pair_missions)
        pair_mission = PairMission(
            pair_id=pair_id,
            mission_text=mission_text,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        self.db_session.add(pair_mission)
        await self.db_session.commit()
        await self.db_session.refresh(pair_mission)
        return pair_mission

    async def get_active_pair_mission(self, pair_id: int) -> Optional[PairMission]:
        """Получить активную парную миссию"""
        result = await self.db_session.execute(
            select(PairMission).where(
                and_(
                    PairMission.pair_id == pair_id,
                    PairMission.active == True,
                    PairMission.expires_at > datetime.utcnow()
                )
            )
        )
        return result.scalar_one_or_none()

    async def mark_pair_mission_completed(self, pair_mission_id: int, user_id: int, report: str) -> bool:
        """Отметить выполнение парной миссии пользователем"""
        result = await self.db_session.execute(
            select(PairMission).where(PairMission.id == pair_mission_id)
        )
        pair_mission = result.scalar_one_or_none()
        if not pair_mission:
            return False

        if pair_mission.completed_by_user1 and pair_mission.completed_by_user2:
            return False

        if not pair_mission.completed_by_user1:
            pair_mission.completed_by_user1 = True
            pair_mission.user1_report = report
        elif not pair_mission.completed_by_user2:
            pair_mission.completed_by_user2 = True
            pair_mission.user2_report = report

        if pair_mission.completed_by_user1 and pair_mission.completed_by_user2:
            pair_mission.active = False

        await self.db_session.commit()
        return True