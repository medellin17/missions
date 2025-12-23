# models/mission.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from models import Base
from datetime import datetime


class Mission(Base):
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    tags_list = Column(String(500))
    difficulty = Column(String(50), nullable=False)
    points_reward = Column(Integer, default=10)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # ✅ НОВЫЕ КОЛОНКИ ДЛЯ ВЕРСИОНИРОВАНИЯ
    is_archived = Column(Boolean, default=False, server_default='false')
    archived_at = Column(DateTime, nullable=True)
    version = Column(Integer, default=1, server_default='1')
    original_id = Column(Integer, nullable=True)
    
    # ✅ КОЛОНКИ ДЛЯ ГРУПП (уже должны быть в БД)
    group_id = Column(Integer, ForeignKey('mission_groups.id', ondelete='SET NULL'), nullable=True)
    is_group_mission = Column(Boolean, default=False, server_default='false')
    sequence_order = Column(Integer, nullable=True)
    
    # Relationships
    completions = relationship("Completion", back_populates="mission")
    group = relationship("MissionGroup", back_populates="missions")
    
    def __repr__(self):
        return f"<Mission(id={self.id}, text='{self.text[:30]}...', v={self.version})>"
