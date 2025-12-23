# /handlers/theme_week.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from typing import Optional
import logging
from datetime import datetime
from sqlalchemy import select  # ✅ ДОБАВЛЕНО: импорт select

from services.theme_week_service import ThemeWeekService
from services.notification_service import NotificationService
from keyboards.theme_week_kb import (
    get_theme_week_menu_keyboard, 
    get_theme_weeks_list_keyboard, 
    get_theme_week_details_keyboard
)
from models.theme_week import ThemeWeek

router = Router()
logger = logging.getLogger(__name__)

@router.message(Command("theme_week"))
@router.message(Command("themes"))
async def cmd_theme_week(message: Message, db_session):
    """Меню тематических недель"""
    theme_service = ThemeWeekService(db_session)
    
    # Получаем активную тематическую неделю
    active_week = await theme_service.get_active_theme_week()
    upcoming_week = await theme_service.get_upcoming_theme_week()
    
    response = "🎨 *Тематические недели*\n\n"
    
    if active_week:
        days_left = (active_week.end_date - datetime.utcnow()).days + 1
        response += f"🟢 *Текущая неделя: {active_week.theme_name}*\n"
        response += f"{active_week.description}\n"
        response += f"Дней осталось: {max(0, days_left)}\n\n"
    else:
        response += "🟢 *Нет активной тематической недели*\n\n"
    
    if upcoming_week:
        days_to_start = (upcoming_week.start_date - datetime.utcnow()).days + 1
        response += f"📅 *Предстоящая неделя: {upcoming_week.theme_name}*\n"
        response += f"Начало через {max(0, days_to_start)} дней\n\n"
    
    all_weeks = await theme_service.get_all_theme_weeks()
    response += f"Всего тематических недель: {len(all_weeks)}"
    
    await message.answer(response, parse_mode="Markdown", reply_markup=get_theme_week_menu_keyboard())


@router.callback_query(F.data == "current_theme_week")
async def callback_current_theme_week(callback: CallbackQuery, db_session):
    """Показать текущую тематическую неделю"""
    theme_service = ThemeWeekService(db_session)
    active_week = await theme_service.get_active_theme_week()
    
    if not active_week:
        await callback.message.edit_text("❌ Нет активной тематической недели.")
        await callback.answer()
        return
    
    days_left = (active_week.end_date - datetime.utcnow()).days + 1
    tags_text = ", ".join(active_week.tags) if active_week.tags else "Общая тема"
    
    response = f"""
🎨 *Текущая тематическая неделя*

🎯 Название: {active_week.theme_name}
📝 Описание: {active_week.description}
🏷️ Теги: {tags_text}
📅 Длительность: {active_week.start_date.strftime('%d.%m')} - {active_week.end_date.strftime('%d.%m')}
⏳ Дней осталось: {max(0, days_left)}

Используйте /mission для получения тематических миссий!
"""
    
    await callback.message.edit_text(response, parse_mode="Markdown", reply_markup=get_theme_week_details_keyboard(active_week.id))
    await callback.answer()


@router.callback_query(F.data == "all_theme_weeks")
async def callback_all_theme_weeks(callback: CallbackQuery, db_session):
    """Показать все тематические недели"""
    theme_service = ThemeWeekService(db_session)
    all_weeks = await theme_service.get_all_theme_weeks()
    
    if not all_weeks:
        await callback.message.edit_text("❌ Пока не создано ни одной тематической недели.")
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "🎨 *Все тематические недели*",
        parse_mode="Markdown",
        reply_markup=get_theme_weeks_list_keyboard(all_weeks)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("theme_week_"))
async def callback_theme_week_details(callback: CallbackQuery, db_session):
    """Показать детали конкретной тематической недели"""
    theme_week_id = int(callback.data.split("_")[2])
    
    result = await db_session.execute(
        select(ThemeWeek).where(ThemeWeek.id == theme_week_id)
    )
    theme_week = result.scalar_one_or_none()
    
    if not theme_week:
        await callback.answer("❌ Неделя не найдена.", show_alert=True)
        return
    
    status = "🟢 Активна" if theme_week.is_active() else "🟡 Будет" if theme_week.is_upcoming() else "🔴 Завершена"
    days_left = 0
    if theme_week.is_active():
        days_left = (theme_week.end_date - datetime.utcnow()).days + 1
    
    response = f"""
🎨 *Тематическая неделя: {theme_week.theme_name}*

📊 Статус: {status}
📝 Описание: {theme_week.description}
🏷️ Теги: {', '.join(theme_week.tags) if theme_week.tags else 'Общая тема'}
📅 Период: {theme_week.start_date.strftime('%d.%m.%Y')} - {theme_week.end_date.strftime('%d.%m.%Y')}
"""
    
    if theme_week.is_active():
        response += f"⏳ Дней осталось: {max(0, days_left)}"
    
    await callback.message.edit_text(response, parse_mode="Markdown", reply_markup=get_theme_week_details_keyboard(theme_week.id))
    await callback.answer()


@router.callback_query(F.data.startswith("progress_"))
async def callback_theme_week_progress(callback: CallbackQuery, db_session):
    """Показать прогресс пользователя по тематической неделе"""
    theme_week_id = int(callback.data.split("_")[1])
    theme_service = ThemeWeekService(db_session)
    
    progress = await theme_service.get_user_progress(callback.from_user.id, theme_week_id)
    
    if not progress:
        await callback.answer("❌ Вы не участвуете в этой тематической неделе.", show_alert=True)
        return
    
    status = "✅ Завершена!" if progress.is_completed() else "⏳ В процессе"
    
    response = f"""
📊 *Ваш прогресс по неделе*

🎯 Выполнено миссий: {progress.missions_completed}
⭐ Набрано очков: {progress.total_points}
🏆 Статус: {status}

Продолжайте в том же духе!
"""
    
    await callback.message.edit_text(response, parse_mode="Markdown", reply_markup=get_theme_week_details_keyboard(theme_week_id))
    await callback.answer()


@router.callback_query(F.data.startswith("achievements_"))
async def callback_theme_week_achievements(callback: CallbackQuery, db_session):
    """Показать достижения по тематической неделе"""
    theme_week_id = int(callback.data.split("_")[1])
    theme_service = ThemeWeekService(db_session)
    
    achievements = await theme_service.get_week_achievements(theme_week_id)
    progress = await theme_service.get_user_progress(callback.from_user.id, theme_week_id)
    
    if not achievements:
        await callback.answer("❌ У этой недели пока нет достижений.", show_alert=True)
        return
    
    response = "🏆 *Достижения недели*\n\n"
    user_achievements = progress.achievements if progress else []
    
    for achievement in achievements:
        status = "✅" if achievement.name in user_achievements else "⏳"
        response += f"{status} {achievement.icon} {achievement.name}\n"
        response += f"   {achievement.description}\n\n"
    
    await callback.message.edit_text(response, parse_mode="Markdown", reply_markup=get_theme_week_details_keyboard(theme_week_id))
    await callback.answer()


@router.callback_query(F.data.startswith("leaderboard_"))
async def callback_theme_week_leaderboard(callback: CallbackQuery, db_session):
    """Показать таблицу лидеров тематической недели"""
    theme_week_id = int(callback.data.split("_")[1])
    theme_service = ThemeWeekService(db_session)
    
    leaderboard = await theme_service.get_leaderboard(theme_week_id)
    
    if not leaderboard:
        await callback.message.edit_text("📊 Таблица лидеров пока пуста.")
        await callback.answer()
        return
    
    response = "🏆 *Таблица лидеров*\n\n"
    for entry in leaderboard:
        position_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(entry['position'], f"{entry['position']}.")
        response += f"{position_emoji} ID: {entry['user_id']}\n"
        response += f"   Очки: {entry['points']} | Миссий: {entry['missions_completed']}\n"
        if entry['completed']:
            response += "   ✅ Завершена\n"
        response += "\n"
    
    await callback.message.edit_text(response, parse_mode="Markdown", reply_markup=get_theme_week_details_keyboard(theme_week_id))
    await callback.answer()


@router.message(Command("theme_help"))
async def cmd_theme_help(message: Message):
    """Справка по тематическим неделям"""
    help_text = """
🎨 *Справка по тематическим неделям:*

• /theme_week - меню тематических недель
• /themes - альтернативная команда
• /theme_help - эта справка

💡 *Как это работает:*

- Раз в неделю запускается тематическая неделя
- Миссии связаны с определенной темой
- За выполнение начисляются специальные очки
- Можно заработать достижения и попасть в таблицу лидеров
- Завершите неделю, выполнив 7 миссий или набрав 100 очков
"""
    
    await message.answer(help_text, parse_mode="Markdown", reply_markup=get_theme_week_menu_keyboard())


# ✅ УДАЛЕНО: Конфликтная функция cmd_mission_theme_integration
# Она конфликтовала с handlers/mission.py