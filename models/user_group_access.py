# models/user_group_access.py

from sqlalchemy import Column, Integer, BigInteger, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from models import Base


class UserGroupAccess(Base):
    """Доступ пользователей к приватным группам"""
    __tablename__ = "user_group_access"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("mission_groups.id"), nullable=False, index=True)
    
    # Кто и когда выдал доступ
    granted_by = Column(BigInteger, nullable=True)  # ID админа
    granted_at = Column(DateTime, default=datetime.utcnow)
    
    # Опциональное ограничение по времени
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    group = relationship("MissionGroup", back_populates="user_accesses")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'group_id', name='uq_user_group_access'),
    )
    
    def __repr__(self):
        return f"<UserGroupAccess user_id={self.user_id} group_id={self.group_id}>"
