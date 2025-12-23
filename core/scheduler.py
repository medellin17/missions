#/core/scheduler.py
import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Dict, Any
import pytz
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from core.config import settings
from services.notification_service import NotificationService
from services.user_service import UserService
from services.pair_service import PairService
from models.notification import UserNotificationSettings
from sqlalchemy import select, and_, func
from core.database import AsyncSessionLocal
from models.user import User  # Добавляем импорт User


class NotificationScheduler:
    def __init__(self):
        self.bot = Bot(token=settings.BOT_TOKEN)
        self.logger = logging.getLogger(__name__)
        self.running = False
    
    async def start_scheduler(self):
        """Запустить планировщик уведомлений"""
        self.running = True
        self.logger.info("Starting notification scheduler...")
        
        # Немного подождем перед началом работы, чтобы дать время на инициализацию базы данных
        await asyncio.sleep(5)
        
        tasks = [
            self.run_notification_sender(),
            self.run_daily_tasks(),
            self.run_weekly_tasks()
        ]
        
        await asyncio.gather(*tasks)
    
    async def run_notification_sender(self):
        """Цикл отправки уведомлений"""
        # Подождем немного перед началом, чтобы убедиться, что таблицы созданы
        await asyncio.sleep(10)
        
        while self.running:
            try:
                async with AsyncSessionLocal() as session:
                    notification_service = NotificationService(session)
                    
                    # Получаем готовые уведомления
                    due_notifications = await notification_service.get_due_notifications()
                    
                    for notification in due_notifications:
                        try:
                            # Отправляем уведомление
                            await self.send_single_notification(notification)
                            
                            # Отмечаем как отправленное
                            await notification_service.mark_notification_as_sent(notification.id)
                            
                        except Exception as e:
                            self.logger.error(f"Failed to send notification {notification.id}: {e}")
                
                # Ждем 30 секунд перед следующей проверкой
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Error in notification sender: {e}")
                await asyncio.sleep(60)
    
    async def send_single_notification(self, notification):
        """Отправить одно уведомление"""
        try:
            if notification.title:
                message = f"*{notification.title}*\n\n{notification.message}"
            else:
                message = notification.message
            
            await self.bot.send_message(
                chat_id=notification.user_id,
                text=message,
                parse_mode="Markdown"
            )
            
        except TelegramAPIError as e:
            self.logger.error(f"Telegram API error for user {notification.user_id}: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error sending notification to {notification.user_id}: {e}")
    
    async def run_daily_tasks(self):
        """Цикл ежедневных задач"""
        while self.running:
            try:
                now = datetime.now()
                # Запланировать задачи на 09:00 по МСК (UTC+3)
                target_time = now.replace(hour=6, minute=0, second=0, microsecond=0)  # 9:00 MSK
                
                if now.time() >= time(6, 0):  # 9:00 MSK
                    target_time += timedelta(days=1)
                
                sleep_seconds = (target_time - now).total_seconds()
                await asyncio.sleep(sleep_seconds)
                
                # Выполнить ежедневные задачи
                await self.execute_daily_tasks()
                
            except Exception as e:
                self.logger.error(f"Error in daily tasks: {e}")
                await asyncio.sleep(3600)  # Ждать час при ошибке
    
    async def run_weekly_tasks(self):
        """Цикл еженедельных задач"""
        while self.running:
            try:
                now = datetime.now()
                # Выполнять в воскресенье в 20:00 по МСК
                target_time = now.replace(hour=17, minute=0, second=0, microsecond=0)  # 20:00 MSK
                days_ahead = 6 - now.weekday()  # 6 = воскресенье
                if days_ahead <= 0:
                    days_ahead += 7
                
                target_time += timedelta(days=days_ahead)
                
                sleep_seconds = (target_time - now).total_seconds()
                await asyncio.sleep(sleep_seconds)
                
                # Выполнить еженедельные задачи
                await self.execute_weekly_tasks()
                
            except Exception as e:
                self.logger.error(f"Error in weekly tasks: {e}")
                await asyncio.sleep(86400)  # Ждать день при ошибке
    
    async def execute_daily_tasks(self):
        """Выполнить ежедневные задачи"""
        self.logger.info("Executing daily notification tasks...")
        
        async with AsyncSessionLocal() as session:
            notification_service = NotificationService(session)
            user_service = UserService(session)
            
            # Получить всех активных пользователей
            try:
                result = await session.execute(
                    select(UserNotificationSettings).where(
                        and_(
                            UserNotificationSettings.enabled == True,
                            UserNotificationSettings.daily_reminders == True
                        )
                    )
                )
                active_users = result.scalars().all()
            except Exception as e:
                self.logger.warning(f"Could not fetch notification settings: {e}")
                active_users = []
                await asyncio.sleep(60)  # Подождать перед следующей попыткой
                return
            
            for user_settings in active_users:
                try:
                    # Проверить, есть ли у пользователя заряды
                    user_result = await session.execute(
                        select(User).where(User.user_id == user_settings.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    
                    if user:
                        # Проверить и сбросить заряды
                        user = await user_service.check_and_reset_charges(user)
                        
                        # Если заряды восстановились, отправить уведомление
                        if user.charges == 3 and user.last_charge_reset.date() == datetime.utcnow().date():
                            await notification_service.send_charge_reminder(user.user_id)
                        
                        # Отправить напоминание, если есть заряды
                        if user.charges > 0:
                            await notification_service.send_daily_reminder(user.user_id)
                
                except Exception as e:
                    self.logger.error(f"Error processing daily task for user {user_settings.user_id}: {e}")
    
    async def execute_weekly_tasks(self):
        """Выполнить еженедельные задачи"""
        self.logger.info("Executing weekly notification tasks...")
        
        async with AsyncSessionLocal() as session:
            notification_service = NotificationService(session)
            pair_service = PairService(session)
            
            # Получить всех активных пользователей
            try:
                result = await session.execute(
                    select(UserNotificationSettings).where(
                        and_(
                            UserNotificationSettings.enabled == True,
                            UserNotificationSettings.weekly_stats == True
                        )
                    )
                )
                active_users = result.scalars().all()
            except Exception as e:
                self.logger.warning(f"Could not fetch notification settings: {e}")
                active_users = []
                await asyncio.sleep(60)  # Подождать перед следующей попыткой
                return
            
            for user_settings in active_users:
                try:
                    # Отправить еженедельную статистику
                    await notification_service.send_weekly_stats(user_settings.user_id)
                    
                    # Проверить активные пары и отправить напоминания
                    active_pair = await pair_service.get_active_pair(user_settings.user_id)
                    if active_pair:
                        partner_id = active_pair.get_partner_id(user_settings.user_id)
                        if partner_id:
                            await notification_service.send_pair_mission_notification(
                                user_settings.user_id, partner_id
                            )
                
                except Exception as e:
                    self.logger.error(f"Error processing weekly task for user {user_settings.user_id}: {e}")
    
    async def stop_scheduler(self):
        """Остановить планировщик"""
        self.running = False
        await self.bot.session.close()
        self.logger.info("Notification scheduler stopped")