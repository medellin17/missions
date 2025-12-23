#/handlers/__init__.py
"""Регистрация всех handlers и роутеров"""

# Основные handlers (явные импорты)
from . import (
    start,
    mission,
    pair,
    notification,
    theme_week,
    mission_groups,
    mission_groups_user,  # ✅ Добавил явно
)

# Admin handlers
from .admin import (
    analytics,
    missions as admin_missions,
    users as admin_users,
)

__all__ = [
    "start",
    "mission",
    "pair",
    "notification",
    "theme_week",
    "mission_groups",
    "mission_groups_user",  # ✅ Было в __all__, но не импортировано в bot/main.py
    "analytics",
    "admin_missions",
    "admin_users",
]