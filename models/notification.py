# models/notification.py
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, Boolean
# УБРАЛИ: from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from typing import Optional

# ДОБАВИЛИ: импорт Base из общего файла
from . import Base # или from models import Base

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    notification_type = Column(String(50), nullable=False)  # daily_reminder, weekly_stats, mission_completed, etc.
    title = Column(String(200))
    message = Column(Text, nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def is_scheduled(self) -> bool:
        return not self.sent and self.scheduled_time > datetime.utcnow()

class UserNotificationSettings(Base):
    __tablename__ = "user_notification_settings"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    enabled = Column(Boolean, default=True)
    daily_reminders = Column(Boolean, default=True)
    weekly_stats = Column(Boolean, default=True)
    mission_notifications = Column(Boolean, default=True)
    pair_notifications = Column(Boolean, default=True)
    timezone_offset = Column(Integer, default=0)  # смещение в часах от UTC
    last_notification_check = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)