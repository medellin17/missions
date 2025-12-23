# services/user_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from typing import Optional
from models.user import User


class UserService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def get_or_create_user(self, user_id: int) -> User:
        """Получить пользователя или создать нового (без commit)"""
        result = await self.db_session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(user_id=user_id)
            self.db_session.add(user)
            # ✅ Только flush, commit сделает вызывающий код
            await self.db_session.flush()
        
        return user
    
    async def check_and_reset_charges(self, user: User) -> User:
        """Проверить и сбросить заряды если нужно (без commit)"""
        now = datetime.utcnow()
        today = now.date()
        
        user_reset_date = user.last_charge_reset.date() if user.last_charge_reset else None
        
        if today != user_reset_date:
            user.charges = 3
            user.last_charge_reset = now
            await self.db_session.flush()
        
        return user
    
    async def consume_charge(self, user: User) -> bool:
        """Уменьшить заряд (без commit)"""
        user = await self.check_and_reset_charges(user)
        
        if user.charges > 0:
            user.charges -= 1
            await self.db_session.flush()
            return True
        
        return False
    
    async def add_points(self, user: User, points: int) -> User:
        """Добавить очки пользователю (без commit)"""
        user.points += points
        user.level = user.points // 100 + 1
        await self.db_session.flush()
        return user