# services/mission_group_service.py

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.mission import Mission
from models.mission_group import AccessType, GroupType, MissionGroup
from models.user import User
from models.user_group_access import UserGroupAccess
from models.user_group_progress import UserGroupProgress

logger = logging.getLogger(__name__)


class MissionGroupService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    # ========== ОСНОВНЫЕ МЕТОДЫ (для пользователей) ==========

    async def get_available_groups(self, user_id: int) -> List[MissionGroup]:
        """
        Получить список доступных групп для пользователя.
        Учитывается: тип доступа, уровень, статус публикации.
        """
        try:
            user_result = await self.db_session.execute(select(User).where(User.user_id == user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                return []

            query = select(MissionGroup).where(
                and_(
                    MissionGroup.is_active == True,
                    MissionGroup.is_published == True,
                )
            )
            result = await self.db_session.execute(query.order_by(MissionGroup.order_index))
            all_groups = result.scalars().all()

            available_groups: List[MissionGroup] = []
            for group in all_groups:
                if await self.check_group_access(user_id, group.id, user.level):
                    available_groups.append(group)

            return available_groups
        except Exception as e:
            logger.error(f"Error getting available groups for user {user_id}: {e}", exc_info=True)
            return []

    async def check_group_access(self, user_id: int, group_id: int, user_level: Optional[int] = None) -> bool:
        """Проверить доступ пользователя к группе."""
        try:
            result = await self.db_session.execute(select(MissionGroup).where(MissionGroup.id == group_id))
            group = result.scalar_one_or_none()
            if not group or not group.is_active or not group.is_published:
                return False

            if user_level is None:
                user_result = await self.db_session.execute(select(User.level).where(User.user_id == user_id))
                user_level = user_result.scalar_one_or_none() or 1

            if group.access_type == AccessType.PUBLIC:
                return True

            if group.access_type == AccessType.LEVEL_BASED:
                return user_level >= group.required_level

            if group.access_type == AccessType.PRIVATE:
                access_result = await self.db_session.execute(
                    select(UserGroupAccess).where(
                        and_(
                            UserGroupAccess.user_id == user_id,
                            UserGroupAccess.group_id == group_id,
                            or_(UserGroupAccess.expires_at.is_(None), UserGroupAccess.expires_at > datetime.utcnow()),
                        )
                    )
                )
                access = access_result.scalar_one_or_none()
                return access is not None

            return False
        except Exception as e:
            logger.error(f"Error checking access for user {user_id} to group {group_id}: {e}", exc_info=True)
            return False

    async def get_group_details(self, group_id: int) -> Optional[MissionGroup]:
        """Получить детали группы."""
        try:
            result = await self.db_session.execute(select(MissionGroup).where(MissionGroup.id == group_id))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting group details {group_id}: {e}", exc_info=True)
            return None

    async def get_group_missions_count(self, group_id: int) -> int:
        """Количество активных миссий в группе."""
        try:
            result = await self.db_session.execute(
                select(func.count(Mission.id)).where(and_(Mission.group_id == group_id, Mission.active == True))
            )
            return result.scalar_one() or 0
        except Exception as e:
            logger.error(f"Error counting missions in group {group_id}: {e}", exc_info=True)
            return 0

    async def get_user_completed_count(self, user_id: int, group_id: int) -> int:
        """Количество выполненных миссий пользователя в группе."""
        try:
            from models.completion import Completion

            result = await self.db_session.execute(
                select(func.count(func.distinct(Completion.mission_id))).where(
                    and_(
                        Completion.telegram_user_id == user_id,
                        Completion.mission_id.in_(select(Mission.id).where(Mission.group_id == group_id)),
                    )
                )
            )
            return result.scalar_one() or 0
        except Exception as e:
            logger.error(f"Error counting completed missions for user {user_id} in group {group_id}: {e}", exc_info=True)
            return 0

    # ========== АДМИНСКИЕ МЕТОДЫ ==========

    async def create_group(
        self,
        name: str,
        description: Optional[str] = None,
        emoji: str = "🎯",
        group_type: GroupType = GroupType.RANDOM,
        access_type: AccessType = AccessType.PUBLIC,
        required_level: int = 1,
        completion_bonus: int = 50,
    ) -> MissionGroup:
        """Создать новую группу."""
        group = MissionGroup(
            name=name,
            description=description,
            emoji=emoji,
            group_type=group_type,
            access_type=access_type,
            required_level=required_level,
            is_active=True,
            is_published=False,
            order_index=0,
            completion_bonus=completion_bonus,
        )
        self.db_session.add(group)
        await self.db_session.commit()
        await self.db_session.refresh(group)
        logger.info(f"Created new group: {name} (ID: {group.id})")
        return group

    async def get_all_groups(self, include_inactive: bool = False) -> List[MissionGroup]:
        """Получить все группы (для админа)."""
        try:
            query = select(MissionGroup) if include_inactive else select(MissionGroup).where(MissionGroup.is_active == True)
            result = await self.db_session.execute(query.order_by(MissionGroup.order_index, MissionGroup.id))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting all groups: {e}", exc_info=True)
            return []

    async def get_group_by_id(self, group_id: int) -> Optional[MissionGroup]:
        """Получить группу по ID."""
        try:
            result = await self.db_session.execute(select(MissionGroup).where(MissionGroup.id == group_id))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting group by id {group_id}: {e}", exc_info=True)
            return None

    async def update_group(
        self,
        group_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        emoji: Optional[str] = None,
        group_type: Optional[GroupType] = None,
        access_type: Optional[AccessType] = None,
        required_level: Optional[int] = None,
        is_published: Optional[bool] = None,
        completion_bonus: Optional[int] = None,
    ) -> bool:
        """Обновить группу."""
        try:
            result = await self.db_session.execute(select(MissionGroup).where(MissionGroup.id == group_id))
            group = result.scalar_one_or_none()
            if not group:
                return False

            if name is not None:
                group.name = name
            if description is not None:
                group.description = description
            if emoji is not None:
                group.emoji = emoji
            if group_type is not None:
                group.group_type = group_type
            if access_type is not None:
                group.access_type = access_type
            if required_level is not None:
                group.required_level = required_level
            if is_published is not None:
                group.is_published = is_published
            if completion_bonus is not None:
                group.completion_bonus = completion_bonus

            group.updated_at = datetime.utcnow()
            await self.db_session.commit()
            logger.info(f"Updated group {group_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating group {group_id}: {e}", exc_info=True)
            await self.db_session.rollback()
            return False

    async def delete_group(self, group_id: int, hard_delete: bool = False) -> bool:
        """Удалить группу (мягкое/жёсткое)."""
        try:
            result = await self.db_session.execute(select(MissionGroup).where(MissionGroup.id == group_id))
            group = result.scalar_one_or_none()
            if not group:
                return False

            if hard_delete:
                await self.db_session.delete(group)
                logger.info(f"Hard deleted group {group_id}")
            else:
                group.is_active = False
                logger.info(f"Soft deleted group {group_id}")

            await self.db_session.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting group {group_id}: {e}", exc_info=True)
            await self.db_session.rollback()
            return False

    async def move_mission_to_group(self, mission_id: int, group_id: Optional[int]) -> bool:
        """Переместить миссию в группу (None = без группы)."""
        try:
            result = await self.db_session.execute(select(Mission).where(Mission.id == mission_id))
            mission = result.scalar_one_or_none()
            if not mission:
                return False

            mission.group_id = group_id
            mission.is_group_mission = group_id is not None
            await self.db_session.commit()
            logger.info(f"Moved mission {mission_id} to group {group_id}")
            return True
        except Exception as e:
            logger.error(f"Error moving mission {mission_id} to group {group_id}: {e}", exc_info=True)
            await self.db_session.rollback()
            return False

    async def get_missions_by_group(self, group_id: Optional[int]) -> List[Mission]:
        """Получить миссии группы."""
        try:
            if group_id is None:
                result = await self.db_session.execute(select(Mission).where(Mission.group_id.is_(None)))
            else:
                result = await self.db_session.execute(
                    select(Mission)
                    .where(Mission.group_id == group_id)
                    .order_by(Mission.sequence_order.nullslast(), Mission.id)
                )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting missions by group {group_id}: {e}", exc_info=True)
            return []

    async def grant_access(
        self,
        user_id: int,
        group_id: int,
        admin_id: Optional[int] = None,
        expires_at: Optional[datetime] = None,
    ) -> bool:
        """Выдать доступ пользователю к приватной группе."""
        try:
            group = await self.get_group_details(group_id)
            if not group:
                return False

            existing = await self.db_session.execute(
                select(UserGroupAccess).where(
                    and_(UserGroupAccess.user_id == user_id, UserGroupAccess.group_id == group_id)
                )
            )
            if existing.scalar_one_or_none():
                logger.info(f"Access already exists for user {user_id} to group {group_id}")
                return True

            access = UserGroupAccess(
                user_id=user_id,
                group_id=group_id,
                granted_by=admin_id,
                granted_at=datetime.utcnow(),
                expires_at=expires_at,
            )
            self.db_session.add(access)
            await self.db_session.commit()
            logger.info(f"Access granted to user {user_id} for group {group_id} by admin {admin_id}")
            return True
        except Exception as e:
            logger.error(f"Error granting access: {e}", exc_info=True)
            await self.db_session.rollback()
            return False

    async def revoke_access(self, user_id: int, group_id: int) -> bool:
        """Отозвать доступ пользователя к группе."""
        try:
            result = await self.db_session.execute(
                select(UserGroupAccess).where(
                    and_(UserGroupAccess.user_id == user_id, UserGroupAccess.group_id == group_id)
                )
            )
            access = result.scalar_one_or_none()
            if not access:
                return False

            await self.db_session.delete(access)
            await self.db_session.commit()
            logger.info(f"Access revoked for user {user_id} to group {group_id}")
            return True
        except Exception as e:
            logger.error(f"Error revoking access: {e}", exc_info=True)
            await self.db_session.rollback()
            return False

    async def get_group_statistics(self, group_id: int) -> Dict[str, Any]:
        """Статистика по группе (для админа)."""
        try:
            started_result = await self.db_session.execute(
                select(func.count(UserGroupProgress.id)).where(UserGroupProgress.group_id == group_id)
            )
            users_started = started_result.scalar_one() or 0

            completed_result = await self.db_session.execute(
                select(func.count(UserGroupProgress.id)).where(
                    and_(UserGroupProgress.group_id == group_id, UserGroupProgress.is_completed == True)
                )
            )
            users_completed = completed_result.scalar_one() or 0

            avg_progress_result = await self.db_session.execute(
                select(func.avg(UserGroupProgress.completed_missions), func.avg(UserGroupProgress.total_missions)).where(
                    UserGroupProgress.group_id == group_id
                )
            )
            avg_data = avg_progress_result.one_or_none()
            avg_completed = float((avg_data[0] or 0) if avg_data else 0)
            avg_total = float((avg_data[1] or 1) if avg_data else 1)

            completion_rate = (users_completed / users_started * 100) if users_started > 0 else 0.0

            return {
                "users_started": users_started,
                "users_completed": users_completed,
                "completion_rate": round(float(completion_rate), 2),
                "avg_progress": f"{avg_completed:.1f}/{avg_total:.1f}",
            }
        except Exception as e:
            logger.error(f"Error getting group statistics {group_id}: {e}", exc_info=True)
            return {"users_started": 0, "users_completed": 0, "completion_rate": 0, "avg_progress": "0/0"}