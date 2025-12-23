# /handlers/notification.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from typing import Optional
import logging
from services.notification_service import NotificationService
from keyboards.notification_kb import get_notification_settings_keyboard
from core.database import get_db_session


router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("notifications"))
async def cmd_notifications(message: Message, db_session):
    """Меню управления уведомлениями"""
    notification_service = NotificationService(db_session)
    
    settings = await notification_service.get_user_settings(message.from_user.id)
    
    status_text = f"""
🔔 *Настройки уведомлений*

Статус: {'✅ Включены' if settings.enabled else '❌ Отключены'}

Ежедневные напоминания: {'✅' if settings.daily_reminders else '❌'}
Еженедельная статистика: {'✅' if settings.weekly_stats else '❌'}
Уведомления о миссиях: {'✅' if settings.mission_notifications else '❌'}
Уведомления о паре: {'✅' if settings.pair_notifications else '❌'}

/toggle_notifications - вкл/выкл все уведомления
/settings_notifications - настроить отдельные типы
/test_notification - отправить тестовое уведомление
"""
    
    await message.answer(status_text, parse_mode="Markdown", reply_markup=get_notification_settings_keyboard())


@router.message(Command("toggle_notifications"))
async def cmd_toggle_notifications(message: Message, db_session):
    """Вкл/выкл все уведомления"""
    notification_service = NotificationService(db_session)
    
    settings = await notification_service.get_user_settings(message.from_user.id)
    new_status = not settings.enabled
    
    updated_settings = await notification_service.update_user_settings(
        message.from_user.id, 
        enabled=new_status
    )
    
    status_text = "✅ Уведомления включены" if new_status else "❌ Уведомления отключены"
    await message.answer(status_text)
    
    # Если включили, отправить тестовое уведомление
    if new_status:
        test_notification = await notification_service.schedule_notification(
            message.from_user.id,
            "welcome",
            "Привет! Уведомления включены. Приятного использования бота!",
            "Добро пожаловать",
            delay_minutes=1
        )


@router.message(Command("settings_notifications"))
async def cmd_settings_notifications(message: Message, db_session):
    """Настроить отдельные типы уведомлений"""
    notification_service = NotificationService(db_session)
    settings = await notification_service.get_user_settings(message.from_user.id)
    
    await message.answer(
        "🔧 *Настройки уведомлений*\n\n"
        "Используйте кнопки ниже для включения/отключения отдельных типов уведомлений:",
        parse_mode="Markdown",
        reply_markup=get_notification_settings_keyboard()
    )


@router.message(Command("test_notification"))
async def cmd_test_notification(message: Message, db_session):
    """Отправить тестовое уведомление"""
    notification_service = NotificationService(db_session)
    
    settings = await notification_service.get_user_settings(message.from_user.id)
    if not settings.enabled:
        await message.answer("❌ Уведомления отключены. Включите их сначала.")
        return
    
    test_notification = await notification_service.schedule_notification(
        message.from_user.id,
        "test",
        "Это тестовое уведомление от Micro-Mission!",
        "Тестовое уведомление",
        delay_minutes=1  # отправим через 1 минуту
    )
    
    if test_notification:
        await message.answer("✅ Тестовое уведомление запланировано и будет отправлено в течение минуты.")
    else:
        await message.answer("❌ Не удалось запланировать тестовое уведомление.")


# Callback хендлеры для кнопок
@router.callback_query(F.data.startswith("toggle_"))
async def callback_toggle_setting(callback: CallbackQuery, db_session):
    """Переключить отдельные настройки"""
    setting_name = callback.data.replace("toggle_", "")
    user_id = callback.from_user.id
    
    notification_service = NotificationService(db_session)
    settings = await notification_service.get_user_settings(user_id)
    
    # Определяем, какое поле нужно изменить
    field_map = {
        "daily": "daily_reminders",
        "weekly": "weekly_stats", 
        "missions": "mission_notifications",
        "pair": "pair_notifications"
    }
    
    if setting_name in field_map:
        field_name = field_map[setting_name]
        current_value = getattr(settings, field_name)
        new_value = not current_value
        
        await notification_service.update_user_settings(user_id, **{field_name: new_value})
        
        status = "включены" if new_value else "отключены"
        await callback.answer(f"{field_name.replace('_', ' ').title()} теперь {status}", show_alert=True)
        
        # Обновляем сообщение
        updated_settings = await notification_service.get_user_settings(user_id)
        await callback.message.edit_reply_markup(
            reply_markup=get_notification_settings_keyboard(updated_settings)
        )
    
    await callback.answer()


@router.callback_query(F.data == "refresh_notifications")
async def callback_refresh_notifications(callback: CallbackQuery, db_session):
    """Обновить клавиатуру уведомлений"""
    notification_service = NotificationService(db_session)
    settings = await notification_service.get_user_settings(callback.from_user.id)
    
    await callback.message.edit_reply_markup(
        reply_markup=get_notification_settings_keyboard(settings)
    )
    await callback.answer()