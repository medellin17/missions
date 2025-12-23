# models/__init__.py
"""
Точка входа для моделей. 
ВАЖНО: Импортируем Base ПЕРВЫМ, затем ВСЕ модели!
"""

# ✅ ШАГ 1: Base из отдельного файла
from models.base import Base, BaseModel

# ✅ ШАГ 2: Импортируем все модели (они автоматически регистрируются в Base. metadata)
from models.user import User
from models.mission import Mission
from models.completion import Completion
from models.pair import Pair, PairRequest
from models.pair_mission import PairMission
from models.notification import Notification
from models.analytics import AdminAnalytics, UserActivityLog, BotPerformance
from models.theme_week import ThemeWeek, UserThemeWeekProgress, ThemeWeekAchievement
from models.mission_group import MissionGroup, GroupType, AccessType
from models.user_group_access import UserGroupAccess
from models.user_group_progress import UserGroupProgress

# ✅ ШАГ 3: Экспортируем все для типизации
__all__ = [
    "Base",
    "BaseModel",
    "User",
    "Mission",
    "Completion",
    "Pair",
    "PairRequest",
    "PairMission",
    "Notification",
    "AdminAnalytics",
    "UserActivityLog",
    "BotPerformance",
    "ThemeWeek",
    "UserThemeWeekProgress",
    "ThemeWeekAchievement",
    "MissionGroup",
    "GroupType",
    "AccessType",
    "UserGroupAccess",
    "UserGroupProgress",
]