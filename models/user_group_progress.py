# models/user_group_progress.py

from sqlalchemy import Column, Integer, BigInteger, ForeignKey, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from models import Base


class UserGroupProgress(Base):
    """Прогресс пользователей в группах миссий"""
    __tablename__ = "user_group_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("mission_groups.id"), nullable=False, index=True)
    
    # Для sequential групп
    current_mission_index = Column(Integer, default=0)  # Текущий индекс миссии
    
    # Общий прогресс
    completed_missions = Column(Integer, default=0)  # Количество выполненных миссий
    total_missions = Column(Integer, default=0)  # Всего миссий в группе
    
    # Статус
    is_completed = Column(Boolean, default=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Статистика
    total_points_earned = Column(Integer, default=0)  # Всего заработано очков в этой группе
    
    # Relationships
    group = relationship("MissionGroup", back_populates="user_progresses")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'group_id', name='uq_user_group_progress'),
    )
    
    def __repr__(self):
        return f"<UserGroupProgress user_id={self.user_id} group_id={self.group_id} {self.completed_missions}/{self.total_missions}>"
