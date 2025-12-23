# /services/completion_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from datetime import datetime, timedelta
from typing import List, Dict, Any
from models.completion import Completion
from models.mission import Mission


class CompletionService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def create_completion(self, user_id: int, mission_text: str, report_type: str, 
                              report_content: str, points_reward: int) -> Completion:
        """Создать запись о выполнении миссии"""
        # В реальном боте здесь нужно будет найти или создать Mission
        # Пока создаем временную запись
        completion = Completion(
            user_id=user_id,
            mission_text=mission_text,  # временное поле, пока не реализована связь с Mission
            report_type=report_type,
            report_content=report_content,
            points_reward=points_reward,
            completed_at=datetime.utcnow()
        )
        
        self.db_session.add(completion)
        await self.db_session.commit()
        await self.db_session.refresh(completion)
        
        return completion
    
    async def update_rating(self, user_id: int, mission_id: int, rating: int):
        """Обновить оценку миссии"""
        result = await self.db_session.execute(
            select(Completion).where(
                Completion.telegram_user_id == user_id,
                Completion.mission_id == mission_id
            ).order_by(desc(Completion.completed_at)).limit(1)
        )
        completion = result.scalar_one_or_none()
        
        if completion:
            completion.rating = rating
            await self.db_session.commit()
    
    async def get_user_completions(self, user_id: int, limit: int = 10) -> List[Completion]:
        """Получить выполненные миссии пользователя"""
        result = await self.db_session.execute(
            select(Completion)
            .where(Completion.telegram_user_id == user_id)
            .order_by(desc(Completion.completed_at))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получить статистику пользователя"""
        # Общее количество выполненных миссий
        total_result = await self.db_session.execute(
            select(func.count(Completion.id)).where(Completion.telegram_user_id == user_id)
        )
        total_completed = total_result.scalar_one()
        
        # Количество за неделю
        week_ago = datetime.utcnow() - timedelta(days=7)
        week_result = await self.db_session.execute(
            select(func.count(Completion.id)).where(
                Completion.telegram_user_id == user_id,
                Completion.completed_at >= week_ago
            )
        )
        week_completed = week_result.scalar_one()
        
        # Лучшая серия (реализация упрощенная)
        # В реальном боте нужно анализировать даты выполнения
        best_streak = 1  # Заглушка
        
        return {
            'total_completed': total_completed,
            'week_completed': week_completed,
            'best_streak': best_streak
        }