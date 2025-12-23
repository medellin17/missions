# models/theme_week.py
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, Boolean, ForeignKey
from datetime import datetime
from typing import Optional, List
import json

from . import Base

class ThemeWeek(Base):
    __tablename__ = "theme_weeks"

    id = Column(Integer, primary_key=True)
    theme_name = Column(String(100), nullable=False)
    description = Column(Text)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    tags_list = Column(Text, default='[]')  # ✅ ИСПРАВЛЕНО: JSON-строка
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    featured = Column(Boolean, default=False)

    # ✅ ДОБАВЛЕНО: Property для работы с tags как list
    @property
    def tags(self) -> List[str]:
        """Десериализация tags из JSON"""
        if not self.tags_list:
            return []
        try:
            return json.loads(self.tags_list)
        except (json.JSONDecodeError, TypeError):
            return []
    
    @tags.setter
    def tags(self, value: List[str]):
        """Сериализация tags в JSON"""
        self.tags_list = json.dumps(value) if value else '[]'

    def is_active(self) -> bool:
        now = datetime.utcnow()
        return self.active and self.start_date <= now <= self.end_date

    def is_upcoming(self) -> bool:
        now = datetime.utcnow()
        return self.active and self.start_date > now

    def is_finished(self) -> bool:
        now = datetime.utcnow()
        return now > self.end_date


class UserThemeWeekProgress(Base):
    __tablename__ = "user_theme_week_progress"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False)
    theme_week_id = Column(Integer, nullable=False)
    missions_completed = Column(Integer, default=0)
    total_points = Column(Integer, default=0)
    achievements_list = Column(Text, default='[]')  # ✅ ИСПРАВЛЕНО: JSON-строка
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    bonus_earned = Column(Boolean, default=False)

    # ✅ ДОБАВЛЕНО: Property для работы с achievements как list
    @property
    def achievements(self) -> List[str]:
        """Десериализация achievements из JSON"""
        if not self.achievements_list:
            return []
        try:
            return json.loads(self.achievements_list)
        except (json.JSONDecodeError, TypeError):
            return []
    
    @achievements.setter
    def achievements(self, value: List[str]):
        """Сериализация achievements в JSON"""
        self.achievements_list = json.dumps(value) if value else '[]'

    def is_completed(self) -> bool:
        return self.completed_at is not None


class ThemeWeekAchievement(Base):
    __tablename__ = "theme_week_achievements"

    id = Column(Integer, primary_key=True)
    theme_week_id = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    condition = Column(String(100), nullable=False)
    points_required = Column(Integer, default=0)
    missions_required = Column(Integer, default=0)
    icon = Column(String(50), default="🏆")
    created_at = Column(DateTime, default=datetime.utcnow)
