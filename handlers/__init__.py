#/handlers/__init__.py
"""Регистрация всех handlers и роутеров"""

# Основные handlers
from .  import start, mission, pair, notification, theme_week, mission_groups

# Admin handlers (из отдельной папки)
from .admin import analytics, missions, users

__all__ = [
    "start",
    "mission",
    "pair",
    "notification",
    "theme_week",
    "mission_groups",
    "analytics",
    "missions",
    "users",
]