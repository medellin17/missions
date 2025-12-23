#/core/scheduler.py
"""
Планировщик фоновых задач: 
- Отправка уведомлений
- Ежедневные напоминания  
- Еженедельная статистика
- Очистка истекших данных
- Автопереключение тематических недель
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import AsyncSessionLocal
from models.notification import Notification
from models.user import User
from models.theme_week import ThemeWeek
from models.pair import Pair, PairRequest
from services.notification_service import NotificationService
from services.pair_service import PairService


logger = logging.getLogger(__name__)


class NotificationScheduler:
    """Планировщик для отправки уведомлений и выполнения фоновых задач"""
    
    def __init__(self):
        """Инициализация планировщика"""
        self. bot = Bot(token=settings.BOT_TOKEN)
        self.logger = logging.getLogger(__name__)
        self.running = False

    async def start_scheduler(self) -> None:
        """Запустить планировщик (запускается параллельно с polling)"""
        self.running = True
        self.logger.info("✅ Notification Scheduler started")
        
        tasks = [
            self.run_notification_sender(),
            self.run_daily_tasks(),
            self.run_weekly_tasks(),
            self.run_cleanup_tasks(),
            self.run_theme_week_switch(),
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            self.logger.info("Scheduler tasks cancelled")
        except Exception as e:
            self.logger.error(f"Scheduler error: {e}", exc_info=True)
    
    async def run_notification_sender(self) -> None:
        """
        Фоновая задача:  отправка уведомлений каждые 30 секунд
        Получает все готовые уведомления и отправляет их через Telegram API
        """
        while self. running:
            try:
                async with AsyncSessionLocal() as session:
                    notification_service = NotificationService(session)
                    
                    # Получаем все готовые к отправке уведомления
                    due_notifications = await notification_service. get_due_notifications()
                    
                    if due_notifications:
                        self.logger.info(f"📤 Sending {len(due_notifications)} notifications...")
                        
                        for notification in due_notifications:
                            try:
                                # Формируем сообщение
                                message_text = self._format_notification(notification)
                                
                                # Отправляем через Telegram API
                                await self.bot.send_message(
                                    chat_id=notification.user_id,
                                    text=message_text,
                                    parse_mode="HTML"
                                )
                                
                                # Отмечаем как отправленное
                                await notification_service.mark_notification_as_sent(notification.id)
                                
                                self.logger.debug(
                                    f"✅ Notification sent to {notification.user_id} "
                                    f"(type: {notification.notification_type})"
                                )
                                
                            except Exception as e:  
                                self.logger. error(
                                    f"❌ Failed to send notification {notification.id} "
                                    f"to user {notification.user_id}: {e}"
                                )
                        
                        await session.commit()
                
                # Ждем 30 секунд перед следующей проверкой
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Error in notification sender loop: {e}", exc_info=True)
                await asyncio. sleep(30)

    async def run_daily_tasks(self) -> None:
        """
        Фоновая задача: ежедневные напоминания и сброс зарядов в 00:00 UTC
        """
        while self. running:
            try:
                now = datetime.utcnow()
                
                # Проверяем если текущее время близко к 00:00 UTC (00:00-00:05)
                if now.hour == 0 and now.minute < 5:
                    self.logger.info("⏰ Running daily tasks...")
                    
                    async with AsyncSessionLocal() as session:
                        await self._send_daily_reminders_to_all(session)
                        await self._reset_charges_for_all(session)
                    
                    # Ждем 5 минут чтобы не повторять задачу
                    await asyncio.sleep(300)
                else:
                    # Ждем 1 минуту перед следующей проверкой
                    await asyncio.sleep(60)
                    
            except Exception as e: 
                self.logger.error(f"Error in daily tasks loop: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def run_weekly_tasks(self) -> None:
        """
        Фоновая задача: еженедельная статистика по понедельникам в 00:00 UTC
        """
        while self.running:
            try:
                now = datetime.utcnow()
                
                # Проверяем если понедельник (weekday 0) и примерно 00:00 UTC
                if now.weekday() == 0 and now.hour == 0 and now.minute < 5:
                    self.logger.info("📊 Running weekly tasks...")
                    
                    async with AsyncSessionLocal() as session:
                        await self._send_weekly_stats_to_all(session)
                    
                    await asyncio.sleep(300)
                else:
                    await asyncio.sleep(3600)  # Проверяем раз в час
                    
            except Exception as e:
                self.logger. error(f"Error in weekly tasks loop: {e}", exc_info=True)
                await asyncio.sleep(3600)

    async def run_cleanup_tasks(self) -> None:
        """
        Фоновая задача: очистка истекших пар и запросов каждый час
        """
        while self.running:
            try:
                await asyncio.sleep(3600)  # Каждый час
                
                self.logger.info("🧹 Running cleanup tasks...")
                
                async with AsyncSessionLocal() as session:
                    pair_service = PairService(session)
                    
                    # Очищаем истекшие запросы
                    await pair_service.cleanup_expired_requests()
                    
                    # Очищаем истекшие пары
                    await pair_service.cleanup_expired_pairs()
                    
                    self.logger.info("✅ Cleanup completed")
                    
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}", exc_info=True)

    async def run_theme_week_switch(self) -> None:
        """
        Фоновая задача: автопереключение тематических недель каждый день в 00:00 UTC
        Проверяет какая неделя активна сейчас и отправляет уведомление пользователям
        """
        while self. running:
            try:
                now = datetime.utcnow()
                
                # Проверяем если это примерно 00:00 UTC (00:00-00:05)
                if now.hour == 0 and now.minute < 5:
                    self.logger. info("⏰ Checking theme week switch...")
                    
                    async with AsyncSessionLocal() as session:
                        # Получаем активную неделю (по дате)
                        week_result = await session.execute(
                            select(ThemeWeek).where(
                                and_(
                                    ThemeWeek.active == True,
                                    ThemeWeek.start_date <= now,
                                    ThemeWeek.end_date >= now
                                )
                            ).order_by(ThemeWeek. start_date.desc())
                        )
                        active_week = week_result.scalar_one_or_none()
                        
                        if active_week: 
                            self.logger.info(f"🎨 Active theme week: {active_week. theme_name}")
                            
                            # Получаем всех пользователей с включенными уведомлениями
                            user_result = await session.execute(
                                select(User).where(User.user_id.isnot(None))
                            )
                            users = user_result.scalars().all()
                            
                            notification_service = NotificationService(session)
                            sent_count = 0
                            
                            for user in users: 
                                try:
                                    # Проверяем настройки уведомлений
                                    settings_obj = await notification_service.get_user_settings(user.user_id)
                                    if not settings_obj. enabled:
                                        continue
                                    
                                    # Создаем уведомление о теме недели
                                    tags_str = ", ".join(active_week.tags) if active_week.tags else "разное"
                                    
                                    message = (
                                        f"🎨 <b>Новая тематическая неделя!</b>\n\n"
                                        f"<b>{active_week.theme_name}</b>\n\n"
                                        f"{active_week.description or 'Выполняйте миссии в этой тематике!'}\n\n"
                                        f"🏷 Теги: {tags_str}\n"
                                        f"🎁 Бонус: доп. очки за миссии на тему недели!"
                                    )
                                    
                                    await notification_service.schedule_notification(
                                        user.user_id,
                                        "theme_week_start",
                                        message,
                                        title=f"🎨 {active_week.theme_name}"
                                    )
                                    sent_count += 1
                                    
                                except Exception as e:
                                    self.logger.debug(f"Failed to notify user {user.user_id}:  {e}")
                            
                            if sent_count > 0:
                                await session.commit()
                                self.logger.info(f"📤 Sent theme week notifications to {sent_count} users")
                        else:
                            self.logger.warning("⚠️ No active theme week found")
                    
                    # Ждем 5 минут чтобы не повторять
                    await asyncio.sleep(300)
                else:
                    # Ждем 1 минуту перед следующей проверкой
                    await asyncio.sleep(60)
                    
            except Exception as e: 
                self.logger.error(f"Error in theme week switch:  {e}", exc_info=True)
                await asyncio.sleep(60)

    # =========================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # =========================================================================

    async def _send_daily_reminders_to_all(self, session:  AsyncSession) -> None:
        """Отправить ежедневные напоминания всем активным пользователям"""
        try:
            # Получаем всех пользователей с включенными напоминаниями
            result = await session.execute(
                select(User).where(User.user_id.isnot(None))
            )
            users = result.scalars().all()
            
            notification_service = NotificationService(session)
            count = 0
            
            for user in users:
                try: 
                    # Проверяем настройки уведомлений
                    settings_obj = await notification_service.get_user_settings(user.user_id)
                    if not settings_obj.enabled or not settings_obj.daily_reminders:
                        continue
                    
                    # Создаем напоминание
                    await notification_service.send_daily_reminder(user.user_id)
                    count += 1
                    
                except Exception as e:
                    self.logger.debug(f"Failed to send reminder to {user.user_id}: {e}")
            
            if count > 0:
                self.logger.info(f"📤 Sent {count} daily reminders")
                await session.commit()
                
        except Exception as e:
            self.logger.error(f"Error sending daily reminders: {e}", exc_info=True)

    async def _reset_charges_for_all(self, session: AsyncSession) -> None:
        """Сбросить заряды для всех пользователей (восстановить в 00:00)"""
        try:
            from sqlalchemy import update
            
            # Обновляем всех пользователей:  charges = 3, last_charge_reset = now
            await session.execute(
                update(User).values(
                    charges=3,
                    last_charge_reset=datetime.utcnow()
                )
            )
            
            result = await session.execute(select(User))
            affected_rows = len(result.scalars().all())
            
            await session.commit()
            self.logger.info(f"🔋 Reset charges for {affected_rows} users")
            
        except Exception as e:
            self.logger. error(f"Error resetting charges: {e}", exc_info=True)
            await session.rollback()

    async def _send_weekly_stats_to_all(self, session: AsyncSession) -> None:
        """Отправить еженедельную статистику всем пользователям"""
        try:
            result = await session.execute(
                select(User).where(User.user_id.isnot(None))
            )
            users = result. scalars().all()
            
            notification_service = NotificationService(session)
            count = 0
            
            for user in users:
                try:
                    settings_obj = await notification_service. get_user_settings(user. user_id)
                    if not settings_obj.enabled or not settings_obj.weekly_stats:
                        continue
                    
                    await notification_service.send_weekly_stats(user.user_id)
                    count += 1
                    
                except Exception as e:
                    self.logger. debug(f"Failed to send weekly stats to {user.user_id}: {e}")
            
            if count > 0:
                self.logger.info(f"📊 Sent {count} weekly stats")
                await session.commit()
                
        except Exception as e:
            self.logger.error(f"Error sending weekly stats:  {e}", exc_info=True)

    def _format_notification(self, notification: Notification) -> str:
        """
        Форматировать уведомление для Telegram
        
        Args:
            notification: Модель Notification из БД
            
        Returns: 
            Отформатированное сообщение (HTML)
        """
        title = notification.title or "Уведомление"
        message = notification.message
        
        # Простой формат:  заголовок + сообщение
        formatted = f"<b>{title}</b>\n\n{message}"
        
        return formatted

    async def stop(self) -> None:
        """Остановить планировщик"""
        self. logger.info("Stopping scheduler...")
        self.running = False
        if self.bot. session:
            await self.bot. session.close()