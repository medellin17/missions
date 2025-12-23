# services/user_progress_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime
from typing import Optional, List
import random
import logging

from models.user_group_progress import UserGroupProgress
from models.mission_group import MissionGroup, GroupType
from models.mission import Mission
from models.completion import Completion
from models.user import User


logger = logging.getLogger(__name__)


class UserProgressService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def get_or_create_progress(self, user_id: int, group_id: int) -> UserGroupProgress:
        """
        Получить или создать прогресс пользователя в группе
        """
        try:
            # Проверяем существующий прогресс
            result = await self.db_session.execute(
                select(UserGroupProgress).where(
                    and_(
                        UserGroupProgress.user_id == user_id,
                        UserGroupProgress.group_id == group_id
                    )
                )
            )
            progress = result.scalar_one_or_none()
            
            if progress:
                return progress
            
            # Создаём новый прогресс
            # Получаем общее количество миссий в группе
            missions_count_result = await self.db_session.execute(
                select(func.count(Mission.id)).where(
                    and_(
                        Mission.group_id == group_id,
                        Mission.active == True
                    )
                )
            )
            total_missions = missions_count_result.scalar_one() or 0
            
            progress = UserGroupProgress(
                user_id=user_id,
                group_id=group_id,
                current_mission_index=0,
                completed_missions=0,
                total_missions=total_missions,
                is_completed=False,
                started_at=datetime.utcnow()
            )
            
            self.db_session.add(progress)
            await self.db_session.commit()
            await self.db_session.refresh(progress)
            
            logger.info(f"Created new progress for user {user_id} in group {group_id}")
            return progress
            
        except Exception as e:
            logger.error(f"Error getting/creating progress: {e}", exc_info=True)
            await self.db_session.rollback()
            raise
    
    async def get_next_mission(self, user_id: int, group_id: int) -> Optional[Mission]:
        """
        Получить следующую миссию для пользователя
        Логика зависит от типа группы (random vs sequential)
        """
        try:
            # Получаем группу
            group_result = await self.db_session.execute(
                select(MissionGroup).where(MissionGroup.id == group_id)
            )
            group = group_result.scalar_one_or_none()
            
            if not group:
                return None
            
            # Получаем или создаём прогресс
            progress = await self.get_or_create_progress(user_id, group_id)
            
            # Если группа завершена
            if progress.is_completed:
                return None
            
            # RANDOM группа - случайная миссия
            if group.group_type == GroupType.RANDOM:
                return await self._get_random_mission(user_id, group_id)
            
            # SEQUENTIAL группа - по порядку
            elif group.group_type == GroupType.SEQUENTIAL:
                return await self._get_sequential_mission(user_id, group_id, progress)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting next mission for user {user_id} in group {group_id}: {e}")
            return None
    
    async def _get_random_mission(self, user_id: int, group_id: int) -> Optional[Mission]:
        """
        Получить случайную невыполненную миссию из группы
        """
        try:
            # Получаем ID всех выполненных миссий пользователя в этой группе
            completed_result = await self.db_session.execute(
                select(Completion.mission_id).where(
                    and_(
                        Completion.telegram_user_id == user_id,
                        Completion.mission_id.in_(
                            select(Mission.id).where(Mission.group_id == group_id)
                        )
                    )
                )
            )
            completed_ids = [row[0] for row in completed_result.fetchall()]
            
            # Получаем все активные миссии группы, кроме выполненных
            query = select(Mission).where(
                and_(
                    Mission.group_id == group_id,
                    Mission.active == True,
                    Mission.id.notin_(completed_ids) if completed_ids else True
                )
            )
            
            result = await self.db_session.execute(query)
            available_missions = result.scalars().all()
            
            if not available_missions:
                # Все миссии выполнены - можно повторить
                all_missions_result = await self.db_session.execute(
                    select(Mission).where(
                        and_(
                            Mission.group_id == group_id,
                            Mission.active == True
                        )
                    )
                )
                available_missions = all_missions_result.scalars().all()
            
            if not available_missions:
                return None
            
            # Выбираем случайную миссию
            return random.choice(available_missions)
            
        except Exception as e:
            logger.error(f"Error getting random mission: {e}", exc_info=True)
            return None
    
    async def _get_sequential_mission(self, user_id: int, group_id: int, progress: UserGroupProgress) -> Optional[Mission]:
        """
        Получить следующую миссию по порядку (для квестов)
        """
        try:
            # Получаем миссию по текущему индексу
            result = await self.db_session.execute(
                select(Mission).where(
                    and_(
                        Mission.group_id == group_id,
                        Mission.sequence_order == progress.current_mission_index + 1,
                        Mission.active == True
                    )
                )
            )
            mission = result.scalar_one_or_none()
            
            return mission
            
        except Exception as e:
            logger.error(f"Error getting sequential mission: {e}", exc_info=True)
            return None
    
    async def update_progress(self, user_id: int, group_id: int, mission_id: int, points_earned: int) -> bool:
        """
        Обновить прогресс после выполнения миссии
        """
        try:
            progress = await self.get_or_create_progress(user_id, group_id)
            
            # Получаем группу и миссию
            group_result = await self.db_session.execute(
                select(MissionGroup).where(MissionGroup.id == group_id)
            )
            group = group_result.scalar_one_or_none()
            
            if not group:
                return False
            
            # Увеличиваем счётчик выполненных миссий
            progress.completed_missions += 1
            progress.total_points_earned += points_earned
            
            # Для SEQUENTIAL групп - увеличиваем индекс
            if group.group_type == GroupType.SEQUENTIAL:
                progress.current_mission_index += 1
            
            # Проверяем завершение группы
            if progress.completed_missions >= progress.total_missions:
                await self.complete_group(user_id, group_id, progress)
            
            await self.db_session.commit()
            
            logger.info(f"Progress updated for user {user_id} in group {group_id}: {progress.completed_missions}/{progress.total_missions}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating progress: {e}", exc_info=True)
            await self.db_session.rollback()
            return False
    
    async def complete_group(self, user_id: int, group_id: int, progress: UserGroupProgress = None) -> bool:
        """
        Завершить группу и начислить бонус
        """
        try:
            if not progress:
                progress = await self.get_or_create_progress(user_id, group_id)
            
            # Получаем группу для бонуса
            group_result = await self.db_session.execute(
                select(MissionGroup).where(MissionGroup.id == group_id)
            )
            group = group_result.scalar_one_or_none()
            
            if not group:
                return False
            
            # Отмечаем как завершённую
            progress.is_completed = True
            progress.completed_at = datetime.utcnow()
            
            # Начисляем бонус пользователю
            user_result = await self.db_session.execute(
                select(User).where(User.user_id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if user:
                user.points += group.completion_bonus
                user.level = user.points // 100 + 1
                
                progress.total_points_earned += group.completion_bonus
                
                logger.info(f"Group {group_id} completed by user {user_id}. Bonus: {group.completion_bonus} points")
            
            await self.db_session.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error completing group: {e}", exc_info=True)
            await self.db_session.rollback()
            return False
    
    async def reset_progress(self, user_id: int, group_id: int) -> bool:
        """
        Сбросить прогресс пользователя в группе (для повторного прохождения)
        """
        try:
            result = await self.db_session.execute(
                select(UserGroupProgress).where(
                    and_(
                        UserGroupProgress.user_id == user_id,
                        UserGroupProgress.group_id == group_id
                    )
                )
            )
            progress = result.scalar_one_or_none()
            
            if not progress:
                return False
            
            # Сбрасываем прогресс
            progress.current_mission_index = 0
            progress.completed_missions = 0
            progress.is_completed = False
            progress.started_at = datetime.utcnow()
            progress.completed_at = None
            # total_points_earned НЕ сбрасываем - это общая статистика
            
            await self.db_session.commit()
            
            logger.info(f"Progress reset for user {user_id} in group {group_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting progress: {e}", exc_info=True)
            await self.db_session.rollback()
            return False
    
    async def get_progress_details(self, user_id: int, group_id: int) -> Optional[dict]:
        """
        Получить детальную информацию о прогрессе
        """
        try:
            progress = await self.get_or_create_progress(user_id, group_id)
            
            percentage = (progress.completed_missions / progress.total_missions * 100) if progress.total_missions > 0 else 0
            
            return {
                "completed": progress.completed_missions,
                "total": progress.total_missions,
                "percentage": round(percentage, 1),
                "is_completed": progress.is_completed,
                "points_earned": progress.total_points_earned,
                "started_at": progress.started_at,
                "completed_at": progress.completed_at
            }
            
        except Exception as e:
            logger.error(f"Error getting progress details: {e}", exc_info=True)
            return None

    async def mark_mission_completed(
    self,
    user_id: int,
    group_id: int,
    mission_id: int
    ) -> bool:
        """
        Отметить миссию как выполненную и обновить прогресс группы
        
        Returns:
            True если группа полностью завершена, False иначе
        """
        try:
            # Получаем прогресс
            progress = await self.get_or_create_progress(user_id, group_id)
            
            if progress.is_completed:
                logger.warning(f"Group {group_id} already completed by user {user_id}")
                return True
            
            # Увеличиваем счетчик выполненных миссий
            progress.completed_missions = (progress.completed_missions or 0) + 1
            
            # Добавляем очки миссии
            from models. mission import Mission
            mission_result = await self.db_session.execute(
                select(Mission).where(Mission.id == mission_id)
            )
            mission = mission_result. scalar_one_or_none()
            
            if mission:
                progress.points_earned = (progress.points_earned or 0) + mission.points_reward
            
            # Проверяем завершена ли группа полностью
            group_result = await self.db_session.execute(
                select(MissionGroup).where(MissionGroup.id == group_id)
            )
            group = group_result.scalar_one_or_none()
            
            is_group_completed = False
            
            if group and progress.completed_missions >= progress.total_missions:
                progress.is_completed = True
                progress.completed_at = datetime.utcnow()
                progress. bonus_earned = True
                is_group_completed = True
                
                logger.info(f"✅ Group {group_id} completed by user {user_id}")
                
                # Добавляем бонус пользователю
                if group.completion_bonus and group.completion_bonus > 0:
                    user_result = await self.db_session.execute(
                        select(User).where(User.user_id == user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    
                    if user: 
                        user.points = (user.points or 0) + group.completion_bonus
                        logger.info(
                            f"🎁 Awarded {group.completion_bonus} bonus points "
                            f"to user {user_id} for completing group {group_id}"
                        )
            
            await self.db_session.commit()
            return is_group_completed
            
        except Exception as e:
            logger.error(f"Error marking mission completed: {e}", exc_info=True)
            await self.db_session.rollback()
            return False

    async def send_group_completion_notification(
        self,
        user_id: int,
        group_id: int
    ) -> None:
        """
        Отправить поздравительное уведомление при завершении группы
        """
        try: 
            from services.notification_service import NotificationService
            
            # Получаем информацию о группе и прогрессе
            group_result = await self.db_session.execute(
                select(MissionGroup).where(MissionGroup.id == group_id)
            )
            group = group_result.scalar_one_or_none()
            
            progress_result = await self.db_session.execute(
                select(UserGroupProgress).where(
                    and_(
                        UserGroupProgress. user_id == user_id,
                        UserGroupProgress.group_id == group_id
                    )
                )
            )
            progress = progress_result.scalar_one_or_none()
            
            if not group or not progress:
                return
            
            # Формируем текст поздравления
            message = (
                f"🏆 <b>Поздравляем!</b>\n\n"
                f"Вы успешно завершили группу миссий:\n"
                f"<b>{group.emoji} {group.name}</b>\n\n"
                f"📊 Статистика:\n"
                f"✅ Выполнено миссий: {progress.completed_missions}/{progress.total_missions}\n"
                f"⭐ Заработано очков: {progress.points_earned}\n"
                f"🎁 Бонус: +{group.completion_bonus} очков\n\n"
                f"Попробуйте другие группы или возвращайтесь за ежедневными миссиями!"
            )
            
            notification_service = NotificationService(self.db_session)
            await notification_service.schedule_notification(
                user_id,
                "group_completed",
                message,
                title=f"✅ Группа завершена:  {group.name}"
            )
            
            logger.info(f"📤 Sent completion notification for group {group_id} to user {user_id}")
            
        except Exception as e: 
            logger.error(f"Error sending completion notification: {e}", exc_info=True)