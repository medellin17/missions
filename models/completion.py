# models/completion.py

from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, synonym
from datetime import datetime

from models import Base

class Completion(Base):
    __tablename__ = "completions"

    id = Column(Integer, primary_key=True, index=True)

    # DB column: userid  -> Python attribute: telegram_user_id
    telegram_user_id = Column("userid", BigInteger, ForeignKey("users.user_id"), nullable=False)
    userid = synonym("telegram_user_id")  # backward-compat, если где-то ещё осталось

    # DB column: missionid -> Python attribute: mission_id
    mission_id = Column("missionid", Integer, ForeignKey("missions.id"), nullable=False)
    missionid = synonym("mission_id")

    # DB column: completedat -> Python attribute: completed_at
    completed_at = Column("completedat", DateTime, default=datetime.utcnow)
    completedat = synonym("completed_at")

    report_type = Column("reporttype", String(50), nullable=False)
    report_text = Column("reporttext", Text)
    report_file_id = Column("reportfileid", String(255))
    points_reward = Column("pointsreward", Integer, default=10)

    user = relationship("User", back_populates="completions")
    mission = relationship("Mission", back_populates="completions")