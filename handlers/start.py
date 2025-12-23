#/handlers/start.py
"""
Основные команды бота:  /start, /help, профиль, статистика. 
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.completion import Completion
from models.user import User
from services.analytics_service import AnalyticsService
from services.user_service import UserService

router = Router()
logger = logging.getLogger(__name__)


def get_start_keyboard() -> ReplyKeyboardMarkup: 
    """Основное меню бота"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Получить миссию")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🖼 Галерея"), KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие.. .",
    )
    return keyboard


@router.message(Command("start"))
async def cmd_start(message: Message, db_session: AsyncSession) -> None:
    """
    Команда /start — приветствие и инициализация пользователя.
    
    Args:
        message: Telegram сообщение
        db_session: Сессия БД (из middleware)
    """
    try:
        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(message.from_user.id)
        user = await user_service.check_and_reset_charges(user)

        welcome_text = (
            "🎯 <b>Добро пожаловать в Micro-Mission!</b>\n\n"
            "Это геймифицированная система микро-заданий для выхода из рутины.\n\n"
            "📋 <b>Что тебя ждёт:</b>\n"
            "• 🎯 <b>/mission</b> — получить новую миссию (3 в день)\n"
            "• 👤 <b>/profile</b> — твой профиль и прогресс\n"
            "• 📊 <b>/stats</b> — статистика по неделям\n"
            "• 🖼 <b>/gallery</b> — галерея выполненных миссий\n"
            "• ℹ️ <b>/help</b> — справка\n\n"
            f"⚡ <b>У тебя {user.charges}/3 зарядов на сегодня.</b>\n"
            "🕐 Восстановление в 00:00 по МСК."
        )

        await message. answer(welcome_text, parse_mode="HTML", reply_markup=get_start_keyboard())

        # Логируем активность
        try:
            analytics = AnalyticsService(db_session)
            is_new = (user.created_at. date() == datetime.utcnow().date())
            await analytics.log_user_activity(
                user.user_id,
                "bot_start",
                {"first_time": is_new},
            )
        except Exception as analytics_error:
            logger.warning(f"Analytics logging error: {analytics_error}")

        # Коммитим сессию
        await db_session.commit()

    except Exception as e:
        logger.error(f"Error in cmd_start: {e}", exc_info=True)
        await message.answer(
            "🎯 <b>Добро пожаловать в Micro-Mission!</b>\n\n"
            "Используйте /mission для получения новой миссии! ",
            parse_mode="HTML",
            reply_markup=get_start_keyboard(),
        )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Команда /help — справка по командам"""
    help_text = (
        "ℹ️ <b>Справка по командам</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/start — начать работу с ботом\n"
        "/mission — получить новую миссию\n"
        "/profile — посмотреть свой профиль\n"
        "/stats — статистика\n"
        "/gallery — галерея выполненных миссий\n"
        "/help — эта справка\n\n"
        "<b>⚡ Система зарядов:</b>\n"
        "• У вас есть <b>3 заряда в день</b>\n"
        "• Каждая миссия тратит <b>1 заряд</b>\n"
        "• Заряды восстанавливаются в <b>полночь по МСК</b>\n\n"
        "<b>🎁 Награды:</b>\n"
        "⭐ Базовая миссия:  10 очков\n"
        "🔥 Элитная миссия: 20 очков\n"
        "Каждые 100 очков = новый уровень\n\n"
        "<b>📸 Галерея:</b>\n"
        "Все ваши фотоотчеты сохраняются автоматически и доступны в /gallery"
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("profile"))
async def cmd_profile(message: Message, db_session: AsyncSession) -> None:
    """
    Команда /profile — профиль пользователя. 
    """
    try:
        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(message.from_user. id)
        user = await user_service.check_and_reset_charges(user)

        profile_text = (
            "👤 <b>Ваш профиль</b>\n\n"
            f"<b>ID:</b> <code>{user.user_id}</code>\n"
            f"<b>⭐ Уровень:</b> {user. level}\n"
            f"<b>🎯 Очки:</b> {user.points}\n"
            f"<b>⚡ Заряды:</b> {user. charges}/3\n"
            f"<b>📅 Присоединился:</b> {user.created_at.strftime('%d.%m.%Y')}\n"
        )

        await message.answer(profile_text, parse_mode="HTML")
        await db_session.commit()

    except Exception as e:
        logger.error(f"Error in cmd_profile: {e}", exc_info=True)
        await message.answer("❌ Ошибка при получении профиля.")


@router.message(Command("stats"))
async def cmd_stats(message: Message, db_session: AsyncSession) -> None:
    """
    Команда /stats — статистика пользователя.
    """
    try:
        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(message.from_user.id)
        user = await user_service.check_and_reset_charges(user)

        # Получаем количество выполненных миссий
        result = await db_session.execute(
            select(func.count(Completion.id)).where(
                Completion.telegram_user_id == user.user_id
            )
        )
        total_completed = result.scalar_one_or_none() or 0

        # Прогресс к следующему уровню
        next_level_points = 100
        current_progress = user.points % next_level_points
        progress_percent = int((current_progress / next_level_points) * 100)

        stats_text = (
            "📊 <b>Ваша статистика</b>\n\n"
            f"⭐ <b>Уровень:</b> {user.level}\n"
            f"🎯 <b>Очки:</b> {user.points}\n"
            f"📈 <b>Прогресс к уровню:</b> {current_progress}/100 ({progress_percent}%)\n"
            f"✅ <b>Выполнено миссий:</b> {total_completed}\n"
            f"⚡ <b>Зарядов осталось:</b> {user. charges}/3\n"
        )

        await message.answer(stats_text, parse_mode="HTML")
        await db_session.commit()

    except Exception as e:
        logger.error(f"Error in cmd_stats:  {e}", exc_info=True)
        await message.answer("❌ Ошибка при получении статистики.")


@router.message(F.text == "🎯 Получить миссию")
@router.message(Command("mission"))
async def button_get_mission(message: Message, db_session: AsyncSession) -> None:
    """
    Кнопка "Получить миссию" или команда /mission.
    Перенаправляет в handlers/mission.py
    """
    # Это просто перенаправление, реальная логика в mission.py
    await message.answer("Загружаю миссию...")


@router.message(F.text == "📊 Статистика")
async def button_stats(message: Message, db_session: AsyncSession) -> None:
    """Кнопка меню — статистика"""
    await cmd_stats(message, db_session)


@router.message(F.text == "👤 Профиль")
async def button_profile(message: Message, db_session: AsyncSession) -> None:
    """Кнопка меню — профиль"""
    await cmd_profile(message, db_session)


@router.message(F. text == "ℹ️ Помощь")
async def button_help(message: Message) -> None:
    """Кнопка меню — помощь"""
    await cmd_help(message)


@router.message(F.text == "🖼 Галерея")
async def button_gallery(message: Message, db_session: AsyncSession) -> None:
    """
    Кнопка меню — галерея. 
    Перенаправляет в handlers/mission.py (cmd_gallery)
    """
    await message.answer("Загружаю галерею...")