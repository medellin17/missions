# models/mission_group.py

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from models import Base
import enum


class GroupType(enum.Enum):
    """Типы групп миссий"""
    RANDOM = "random"      # Случайный порядок
    SEQUENTIAL = "sequential"  # Последовательный (квест)


class AccessType(enum.Enum):
    """Типы доступа к группе"""
    PUBLIC = "public"      # Доступна всем
    LEVEL_BASED = "level_based"  # По уровню
    PRIVATE = "private"    # Только по списку


class MissionGroup(Base):
    __tablename__ = "mission_groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    emoji = Column(String(10), default="🎯")
    
    # Тип группы
    group_type = Column(SQLEnum(GroupType), default=GroupType.RANDOM, nullable=False)
    
    # Настройки доступа
    access_type = Column(SQLEnum(AccessType), default=AccessType.PUBLIC, nullable=False)
    required_level = Column(Integer, default=1)  # Минимальный уровень для доступа
    
    # Статус
    is_active = Column(Boolean, default=True)
    is_published = Column(Boolean, default=False)  # Опубликована ли группа
    
    # Отображение
    order_index = Column(Integer, default=0)  # Порядок в списке
    
    # Награды
    completion_bonus = Column(Integer, default=50)  # Бонус за завершение всей группы
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    missions = relationship("Mission", back_populates="group", foreign_keys="Mission.group_id")
    user_accesses = relationship("UserGroupAccess", back_populates="group")
    user_progresses = relationship("UserGroupProgress", back_populates="group")
    
    def __repr__(self):
        return f"<MissionGroup {self.name} ({self.group_type.value})>"
