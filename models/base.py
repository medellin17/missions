#/models/base.py

"""
Базовый класс SQLAlchemy для всех моделей.
Этот файл ДОЛЖЕН быть импортирован ПЕРВЫМ, до всех моделей! 
"""

from sqlalchemy. orm import declarative_base
from sqlalchemy import Column, Integer, DateTime
from datetime import datetime
from typing import Any


# ✅ ЕДИНСТВЕННЫЙ Base в проекте
Base = declarative_base()


class BaseModel(Base):
    """Абстрактный базовый класс для всех моделей с общими полями"""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        """Строковое представление модели"""
        return f"<{self.__class__.__name__}(id={self.id})>"