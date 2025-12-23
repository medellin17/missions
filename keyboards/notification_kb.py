# /keyboards/notification_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from models.notification import UserNotificationSettings


def get_notification_settings_keyboard(settings=None) -> InlineKeyboardMarkup:
    """Клавиатура для настроек уведомлений"""
    builder = InlineKeyboardBuilder()
    
    if settings:
        # Кнопки для отдельных типов уведомлений
        builder.button(
            text=f"📅 Ежедневные ({'✅' if settings.daily_reminders else '❌'})",
            callback_data="toggle_daily"
        )
        builder.button(
            text=f"📊 Еженедельные ({'✅' if settings.weekly_stats else '❌'})",
            callback_data="toggle_weekly"
        )
        builder.button(
            text=f"🎯 Миссии ({'✅' if settings.mission_notifications else '❌'})",
            callback_data="toggle_missions"
        )
        builder.button(
            text=f"🤝 Пара ({'✅' if settings.pair_notifications else '❌'})",
            callback_data="toggle_pair"
        )
        builder.button(
            text="🔄 Обновить",
            callback_data="refresh_notifications"
        )
    else:
        # Кнопки без статуса (для начального отображения)
        builder.button(text="📅 Ежедневные уведомления", callback_data="toggle_daily")
        builder.button(text="📊 Еженедельные уведомления", callback_data="toggle_weekly")
        builder.button(text="🎯 Уведомления о миссиях", callback_data="toggle_missions")
        builder.button(text="🤝 Уведомления о паре", callback_data="toggle_pair")
        builder.button(text="🔄 Обновить", callback_data="refresh_notifications")
    
    builder.adjust(1, 1, 1, 1, 1)
    
    return builder.as_markup()