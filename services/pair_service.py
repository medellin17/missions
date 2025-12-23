# /services/pair_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, delete
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from models.pair import Pair, PairRequest
from models.user import User


class PairService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def create_pair_request(self, from_user_id: int, to_user_id: int) -> bool:
        """Создать запрос на пару"""
        # Проверяем, не существует ли уже активной пары
        existing_pair = await self.get_active_pair(from_user_id)
        if existing_pair:
            return False
        
        # Проверяем, не существует ли уже запроса
        existing_request = await self.get_pending_request(from_user_id, to_user_id)
        if existing_request:
            return False
        
        # Создаем запрос
        request = PairRequest(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            expires_at=datetime.utcnow() + timedelta(hours=24)  # запрос действует 24 часа
        )
        
        self.db_session.add(request)
        await self.db_session.commit()
        return True
    
    async def accept_pair_request(self, to_user_id: int, from_user_id: int) -> bool:
        """Принять запрос на пару"""
        result = await self.db_session.execute(
            select(PairRequest).where(
                and_(
                    PairRequest.from_user_id == from_user_id,
                    PairRequest.to_user_id == to_user_id,
                    PairRequest.status == "pending",
                    PairRequest.expires_at > datetime.utcnow()
                )
            )
        )
        request = result.scalar_one_or_none()
        
        if not request:
            return False
        
        # Обновляем статус запроса
        request.status = "accepted"
        
        # Создаем пару
        pair = Pair(
            user1_id=from_user_id,
            user2_id=to_user_id,
            expires_at=datetime.utcnow() + timedelta(days=7)  # пара действует неделю
        )
        
        self.db_session.add(pair)
        await self.db_session.commit()
        return True
    
    async def decline_pair_request(self, to_user_id: int, from_user_id: int) -> bool:
        """Отклонить запрос на пару"""
        result = await self.db_session.execute(
            update(PairRequest)
            .where(
                and_(
                    PairRequest.from_user_id == from_user_id,
                    PairRequest.to_user_id == to_user_id,
                    PairRequest.status == "pending"
                )
            )
            .values(status="declined")
        )
        
        await self.db_session.commit()
        return result.rowcount > 0
    
    async def get_pending_request(self, from_user_id: int, to_user_id: int) -> Optional[PairRequest]:
        """Получить ожидающий запрос"""
        result = await self.db_session.execute(
            select(PairRequest).where(
                and_(
                    PairRequest.from_user_id == from_user_id,
                    PairRequest.to_user_id == to_user_id,
                    PairRequest.status == "pending"
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_pending_requests_to_user(self, user_id: int) -> List[PairRequest]:
        """Получить все запросы к пользователю"""
        result = await self.db_session.execute(
            select(PairRequest).where(
                and_(
                    PairRequest.to_user_id == user_id,
                    PairRequest.status == "pending",
                    PairRequest.expires_at > datetime.utcnow()
                )
            ).order_by(PairRequest.created_at.desc())
        )
        return result.scalars().all()
    
    async def get_active_pair(self, user_id: int) -> Optional[Pair]:
        """Получить активную пару пользователя"""
        result = await self.db_session.execute(
            select(Pair).where(
                and_(
                    Pair.active == True,
                    Pair.expires_at > datetime.utcnow(),
                    or_(Pair.user1_id == user_id, Pair.user2_id == user_id)
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_pair_by_users(self, user1_id: int, user2_id: int) -> Optional[Pair]:
        """Получить пару по двум пользователям"""
        result = await self.db_session.execute(
            select(Pair).where(
                and_(
                    Pair.active == True,
                    Pair.expires_at > datetime.utcnow(),
                    or_(
                        and_(Pair.user1_id == user1_id, Pair.user2_id == user2_id),
                        and_(Pair.user1_id == user2_id, Pair.user2_id == user1_id)
                    )
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def remove_pair(self, user_id: int) -> bool:
        """Удалить пару пользователя"""
        pair = await self.get_active_pair(user_id)
        if not pair:
            return False
        
        pair.active = False
        await self.db_session.commit()
        return True
    
    async def cleanup_expired_requests(self):
        """Очистить истекшие запросы"""
        await self.db_session.execute(
            delete(PairRequest).where(
                and_(
                    PairRequest.status == "pending",
                    PairRequest.expires_at <= datetime.utcnow()
                )
            )
        )
        await self.db_session.commit()
    
    async def cleanup_expired_pairs(self):
        """Очистить истекшие пары"""
        await self.db_session.execute(
            update(Pair)
            .where(Pair.expires_at <= datetime.utcnow())
            .values(active=False)
        )
        await self.db_session.commit()