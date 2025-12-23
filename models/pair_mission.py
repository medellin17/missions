# models/pair_mission.py
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Text, Boolean, ForeignKey
# УБРАЛИ: from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from typing import Optional

# ДОБАВИЛИ: импорт Base из общего файла
from . import Base # или from models import Base

class PairMission(Base):
    __tablename__ = "pair_missions"
    
    id = Column(Integer, primary_key=True)
    pair_id = Column(Integer, nullable=False)  # ID из таблицы pairs
    mission_text = Column(Text, nullable=False)  # Текст парной миссии
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # Время выполнения миссии
    completed_by_user1 = Column(Boolean, default=False)
    completed_by_user2 = Column(Boolean, default=False)
    user1_report = Column(Text)
    user2_report = Column(Text)
    active = Column(Boolean, default=True)

class PairMissionCompletion(Base):
    __tablename__ = "pair_mission_completions"
    
    id = Column(Integer, primary_key=True)
    pair_mission_id = Column(Integer, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    report_type = Column(String(10))  # "text", "photo", "both"
    report_content = Column(Text)
    completed_at = Column(DateTime, default=datetime.utcnow)
    rating = Column(Integer, nullable=True)  # 1-5