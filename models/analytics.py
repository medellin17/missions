# models/analytics.py
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Float, Text, Boolean, ForeignKey
# УБРАЛИ: from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import relationship # если будут relationship
from datetime import datetime
# УБРАЛИ: import json # если не используется в этом файле

# ДОБАВИЛИ: импорт Base из общего файла
from . import Base # или from models import Base

# УБРАЛИ: class User(Base): ... (определена в models/user.py)
# УБРАЛИ: class Mission(Base): ... (определена в models/mission.py)
# УБРАЛИ: class Completion(Base): ... (определена в models/completion.py)

class AdminAnalytics(Base):
    __tablename__ = "admin_analytics"
    
    id = Column(Integer, primary_key=True)
    metric_name = Column(String(100), nullable=False)  # "daily_active_users", "missions_completed", etc.
    date = Column(DateTime, default=datetime.utcnow)
    value = Column(Float, nullable=False)
    metric_metadata = Column(Text)  # переименовано из metadata


class UserActivityLog(Base):
    __tablename__ = "user_activity_logs"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    action = Column(String(100), nullable=False)  # "mission_request", "mission_completion", "pair_creation", etc.
    action_details = Column(Text)  # переименовано из details
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45))  # IP адрес (если доступен)
    user_agent = Column(Text)  # User-Agent (если доступен)


class BotPerformance(Base):
    __tablename__ = "bot_performance"
    
    id = Column(Integer, primary_key=True)
    metric_type = Column(String(50), nullable=False)  # "response_time", "error_rate", "uptime", etc.
    value = Column(Float, nullable=False)
    unit = Column(String(20))  # "seconds", "percentage", etc.
    timestamp = Column(DateTime, default=datetime.utcnow)
    performance_metadata = Column(Text)  # переименовано из metadata


class AdminDashboard(Base):
    __tablename__ = "admin_dashboards"
    
    id = Column(Integer, primary_key=True)
    admin_user_id = Column(BigInteger, nullable=False)  # ID администратора
    dashboard_config = Column(Text)  # настройки дашборда (вместо JSON, для избежания конфликта)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)