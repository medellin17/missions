# /keyboards/theme_week_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List
from models.theme_week import ThemeWeek


def get_theme_week_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для меню тематических недель"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🎯 Текущая неделя", callback_data="current_theme_week")
    builder.button(text="📅 Все недели", callback_data="all_theme_weeks")
    builder.button(text="🏆 Лидеры", callback_data="theme_week_leaderboard")
    builder.button(text="🏠 Назад", callback_data="back_to_main")
    
    builder.adjust(2, 2)
    
    return builder.as_markup()


def get_theme_weeks_list_keyboard(theme_weeks: List[ThemeWeek]) -> InlineKeyboardMarkup:
    """Клавиатура со списком тематических недель"""
    builder = InlineKeyboardBuilder()
    
    for week in theme_weeks:
        status = "🟢" if week.is_active() else "🟡" if week.is_upcoming() else "🔴"
        builder.button(
            text=f"{status} {week.theme_name}",
            callback_data=f"theme_week_{week.id}"
        )
    
    builder.button(text="🏠 Назад", callback_data="back_to_main")
    builder.adjust(1, 1)
    
    return builder.as_markup()


def get_theme_week_details_keyboard(theme_week_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для деталей тематической недели"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="📊 Мой прогресс", callback_data=f"progress_{theme_week_id}")
    builder.button(text="🏆 Достижения", callback_data=f"achievements_{theme_week_id}")
    builder.button(text="🏆 Лидеры", callback_data=f"leaderboard_{theme_week_id}")
    builder.button(text="🏠 Назад", callback_data="all_theme_weeks")
    
    builder.adjust(2, 2)
    
    return builder.as_markup()