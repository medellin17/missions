# models/user.py

from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, JSON
from sqlalchemy.orm import relationship
from models import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, unique=True, nullable=False, index=True)  # ← Telegram ID
    username = Column(String(255), unique=True, nullable=True)
    points = Column(Integer, default=0)
    level = Column(Integer, default=1)
    charges = Column(Integer, default=3)
    last_charge_reset = Column(DateTime, default=datetime.utcnow)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    preferences = Column(JSON, default=dict)
    
    # ✅ RELATIONSHIPS
    # Явно указываем foreign_keys, т.к. Completion.telegram_user_id ссылается на User.user_id, а не User.id
    completions = relationship(
        "Completion", 
        back_populates="user",
        foreign_keys="Completion.telegram_user_id"
    )
    
    def get_level_progress(self):
        """Получить прогресс до следующего уровня"""
        if self.level >= 3:
            return (self.points, self.points)
        
        current_score = self.points % 100
        next_level_score = 100
        
        return (current_score, next_level_score)
