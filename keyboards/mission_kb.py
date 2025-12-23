# keyboards/mission_kb.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню бота"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎯 Получить миссию", callback_data="get_mission")
    builder.button(text="👤 Мой профиль", callback_data="my_profile")
    builder.button(text="🎲 Группы миссий", callback_data="show_groups")  # ✅ ДОБАВЛЕНО
    builder.button(text="🤝 Парные миссии", callback_data="pair_missions")
    builder.button(text="🎨 Тематические недели", callback_data="theme_weeks")
    builder.button(text="ℹ️ Помощь", callback_data="help")
    builder.adjust(2, 2, 2)  # ✅ ИЗМЕНЕНО: теперь 2+2+2 вместо 2+2+1
    return builder.as_markup()


def get_difficulty_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора сложности миссии"""
    builder = InlineKeyboardBuilder()
    builder.button(text="⭐ Базовая (10 очков)", callback_data="difficulty_basic")
    builder.button(text="🔥 Элитная (20 очков)", callback_data="difficulty_elite")
    builder.button(text="❌ Отмена", callback_data="mission_cancel")
    builder.adjust(1)
    return builder.as_markup()


def get_mission_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после получения миссии"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выполнить миссию", callback_data="mission_done")
    builder.button(text="⏭ Пропустить", callback_data="mission_skip")
    builder.button(text="ℹ️ Помощь", callback_data="mission_help")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_mission_action_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура действий с миссией"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Отправить отчет", callback_data="mission_report")
    builder.button(text="⏭ Пропустить", callback_data="mission_skip")
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_report_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения отчета"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="report_confirm")
    builder.button(text="✏️ Изменить", callback_data="report_edit")
    builder.button(text="❌ Отмена", callback_data="report_cancel")
    builder.adjust(2, 1)
    return builder.as_markup()


# ✅ НОВАЯ ФУНКЦИЯ для возврата в главное меню из групп
def get_back_to_main_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Главное меню", callback_data="main_menu")
    return builder.as_markup()
