# /services/notification_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import asyncio
import logging
from models.notification import Notification, UserNotificationSettings
from models.user import User
from models.completion import Completion
from models.pair import Pair


class NotificationService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.logger = logging.getLogger(__name__)
    
    async def get_user_settings(self, user_id: int) -> UserNotificationSettings:
        """Получить настройки уведомлений пользователя"""
        result = await self.db_session.execute(
            select(UserNotificationSettings).where(UserNotificationSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()
        
        if not settings:
            settings = UserNotificationSettings(user_id=user_id)
            self.db_session.add(settings)
            await self.db_session.commit()
        
        return settings
    
    async def update_user_settings(self, user_id: int, **kwargs) -> UserNotificationSettings:
        """Обновить настройки уведомлений пользователя"""
        settings = await self.get_user_settings(user_id)
        
        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        
        settings.updated_at = datetime.utcnow()
        await self.db_session.commit()
        return settings
    
    async def schedule_notification(self, user_id: int, notification_type: str, 
                                  message: str, title: Optional[str] = None, 
                                  delay_minutes: int = 0) -> Notification:
        """Запланировать уведомление"""
        scheduled_time = datetime.utcnow() + timedelta(minutes=delay_minutes)
        
        notification = Notification(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            scheduled_time=scheduled_time
        )
        
        self.db_session.add(notification)
        await self.db_session.commit()
        await self.db_session.refresh(notification)
        
        return notification
    
    async def get_due_notifications(self) -> List[Notification]:
        """Получить уведомления, готовые к отправке"""
        result = await self.db_session.execute(
            select(Notification).where(
                and_(
                    Notification.sent == False,
                    Notification.scheduled_time <= datetime.utcnow()
                )
            )
        )
        return result.scalars().all()
    
    async def mark_notification_as_sent(self, notification_id: int) -> bool:
        """Отметить уведомление как отправленное"""
        result = await self.db_session.execute(
            update(Notification)
            .where(Notification.id == notification_id)
            .values(sent=True, sent_at=datetime.utcnow())
        )
        
        await self.db_session.commit()
        return result.rowcount > 0
    
    async def send_daily_reminder(self, user_id: int) -> Optional[Notification]:
        """Запланировать ежедневное напоминание"""
        settings = await self.get_user_settings(user_id)
        if not settings.enabled or not settings.daily_reminders:
            return None
        
        # Проверяем, есть ли у пользователя заряды
        result = await self.db_session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user and user.charges > 0:
            message = f"🔔 Привет! У вас {user.charges}/3 зарядов на сегодня. Не забудьте получить миссию командой /mission!"
            return await self.schedule_notification(user_id, "daily_reminder", message, "Напоминание о миссии")
        return None
    
    async def send_weekly_stats(self, user_id: int) -> Optional[Notification]:
        """Запланировать еженедельную статистику"""
        settings = await self.get_user_settings(user_id)
        if not settings.enabled or not settings.weekly_stats:
            return None
        
        # Получаем статистику за неделю
        week_ago = datetime.utcnow() - timedelta(days=7)
        result = await self.db_session.execute(
            select(func.count(Completion.id)).where(
                and_(
                    Completion.user_id == user_id,
                    Completion.completed_at >= week_ago
                )
            )
        )
        week_completed = result.scalar_one()
        
        result = await self.db_session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            message = f"""
📊 *Еженедельная статистика*

🎯 Выполнено миссий за неделю: {week_completed}
⭐ Очков за неделю: {week_completed * 10 if week_completed else 0}
👤 Уровень: {user.level}
⚡ Зарядов осталось: {user.charges}/3

Продолжайте в том же духе!
"""
            return await self.schedule_notification(
                user_id, "weekly_stats", message, "Еженедельная статистика", delay_minutes=1
            )
        return None
    
    async def send_mission_completed_notification(self, user_id: int, points: int) -> Optional[Notification]:
        """Отправить уведомление о выполнении миссии"""
        settings = await self.get_user_settings(user_id)
        if not settings.enabled or not settings.mission_notifications:
            return None
        
        result = await self.db_session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            message = f"🎉 Миссия выполнена! +{points} очков\nТекущий уровень: {user.level}"
            return await self.schedule_notification(
                user_id, "mission_completed", message, "Миссия выполнена"
            )
        return None
    
    async def send_pair_mission_notification(self, user_id: int, partner_id: int) -> Optional[Notification]:
        """Отправить уведомление о парной миссии"""
        settings = await self.get_user_settings(user_id)
        if not settings.enabled or not settings.pair_notifications:
            return None
        
        message = f"🤝 У вас новая парная миссия с пользователем {partner_id}! Проверьте командой /pair_mission"
        return await self.schedule_notification(
            user_id, "pair_mission", message, "Новая парная миссия"
        )
    
    async def send_charge_reminder(self, user_id: int) -> Optional[Notification]:
        """Отправить напоминание о восстановлении зарядов"""
        settings = await self.get_user_settings(user_id)
        if not settings.enabled or not settings.daily_reminders:
            return None
        
        message = "🔋 Ваши заряды восстановились! Пора за новыми миссиями /mission"
        return await self.schedule_notification(
            user_id, "charge_restored", message, "Заряды восстановлены"
        )
    
    async def cleanup_old_notifications(self, days: int = 7):
        """Очистить старые уведомления"""
        old_date = datetime.utcnow() - timedelta(days=days)
        await self.db_session.execute(
            update(Notification)
            .where(and_(Notification.sent == True, Notification.sent_at <= old_date))
            .values(sent=None)  # или удалить полностью
        )
        await self.db_session.commit()