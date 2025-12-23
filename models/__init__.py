# models/__init__.py
from sqlalchemy.orm import declarative_base

# Общий Base для всех моделей
# ВАЖНО: Это должен быть первым, до любых импортов моделей
Base = declarative_base()

from .user import User
from .mission import Mission
from .completion import Completion
from .pair import Pair
from .notification import Notification
from .analytics import AdminAnalytics
from .theme_week import ThemeWeek
from .mission_group import MissionGroup, GroupType, AccessType
from .user_group_access import UserGroupAccess
from .user_group_progress import UserGroupProgress

__all__ = [
    "User",
    "Mission", 
    "Completion",
    "Pair",
    "Notification",
    "AdminAnalytics",
    "ThemeWeek",
    "MissionGroup"  # ✅ И СЮДА
]