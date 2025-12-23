# models/pair.py
from sqlalchemy import Column, Integer, BigInteger, DateTime, Boolean, String
# УБРАЛИ: from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from typing import Optional

# ДОБАВИЛИ: импорт Base из общего файла
from . import Base # или from models import Base

class Pair(Base):
    __tablename__ = "pairs"
    
    id = Column(Integer, primary_key=True)
    user1_id = Column(BigInteger, nullable=False)
    user2_id = Column(BigInteger, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # Время истечения пары
    
    def get_partner_id(self, user_id: int) -> Optional[int]:
        """Получить ID партнера по ID одного из пользователей"""
        if user_id == self.user1_id:
            return self.user2_id
        elif user_id == self.user2_id:
            return self.user1_id
        return None

class PairRequest(Base):
    __tablename__ = "pair_requests"
    
    id = Column(Integer, primary_key=True)
    from_user_id = Column(BigInteger, nullable=False)
    to_user_id = Column(BigInteger, nullable=False)
    status = Column(String(20), default="pending")  # pending, accepted, declined, expired
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)