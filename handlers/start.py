# handlers/start.py

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from datetime import datetime
import logging

from sqlalchemy import func, select

from models.completion import Completion
from services.analytics_service import AnalyticsService
from services.user_service import UserService

router = Router()
logger = logging.getLogger(__name__)


def get_start_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для главного меню."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Получить миссию")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🖼 Галерея"), KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие...",
    )
    return keyboard


@router.message(Command("start"))
async def cmd_start(message: Message, db_session):
    """Приветственное сообщение при старте бота."""
    try:
        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(message.from_user.id)
        user = await user_service.check_and_reset_charges(user)

        welcome_text = (
            "🎯 Добро пожаловать в Micro-Mission!\n\n"
            "Это геймифицированная система микро-заданий для выхода из рутины.\n\n"
            "📋 Доступные команды:\n\n"
            "• /mission - получить новую миссию\n"
            "• /profile - ваш профиль и статистика\n"
            "• /gallery - галерея выполненных миссий\n"
            "• /help - справка\n\n"
            f"⚡ У вас {user.charges}/3 зарядов на сегодня.\n"
            "🕐 Восстановление в 00:00 по МСК."
        )

        await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_start_keyboard())

        # Логируем активность
        try:
            analytics = AnalyticsService(db_session)
            await analytics.log_user_activity(
                user.user_id,
                "bot_start",
                {"first_time": user.created_at.date() == datetime.utcnow().date()},
            )
        except Exception as analytics_error:
            logger.error(f"Analytics logging error: {analytics_error}", exc_info=True)

    except Exception as e:
        logger.error(f"Error in cmd_start: {e}", exc_info=True)
        await message.answer(
            "🎯 Добро пожаловать в Micro-Mission!\n\n"
            "Используйте /mission для получения новой миссии!",
            parse_mode="HTML",
            reply_markup=get_start_keyboard(),
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Справка по командам бота."""
    help_text = (
        "ℹ️ Справка по командам\n\n"
        "Основные команды:\n"
        "/start - начать работу с ботом\n"
        "/mission - получить новую миссию\n"
        "/profile - посмотреть свой профиль\n"
        "/gallery - галерея выполненных миссий\n"
        "/cancel - отменить текущее действие\n"
        "/help - эта справка\n\n"
        "⚡ Система зарядов:\n"
        "• У вас есть 3 заряда в день\n"
        "• Каждая миссия тратит 1 заряд\n"
        "• Заряды восстанавливаются в полночь по МСК\n\n"
        "🎁 Награды:\n"
        "⭐ Базовая миссия: 10 очков\n"
        "🔥 Элитная миссия: 20 очков\n"
        "Каждые 100 очков = новый уровень (до 3)\n"
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(F.text == "🎯 Получить миссию")
async def button_get_mission(message: Message, db_session, state: FSMContext):
    """Кнопка — вызов /mission."""
    from handlers.mission import cmd_mission
    await cmd_mission(message, db_session, state)


@router.message(F.text == "👤 Профиль")
async def button_profile(message: Message, db_session):
    """Кнопка — показ профиля."""
    from handlers.mission import cmd_profile
    await cmd_profile(message, db_session)


@router.message(F.text == "📊 Статистика")
async def button_stats(message: Message, db_session):
    """Кнопка — краткая статистика."""
    try:
        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(message.from_user.id)
        user = await user_service.check_and_reset_charges(user)

        result = await db_session.execute(
            select(func.count(Completion.id)).where(Completion.telegram_user_id == user.user_id)
        )
        total_completed = result.scalar_one_or_none() or 0

        next_level_points = 100
        current_progress = user.points % next_level_points
        progress_percent = int((current_progress / next_level_points) * 100)

        stats_text = (
            "📊 Краткая статистика\n\n"
            f"⭐ Уровень: {user.level}\n"
            f"🎯 Очки: {user.points}\n"
            f"⚡ Заряды: {user.charges}/3\n"
            f"✅ Выполнено миссий: {total_completed}\n"
            f"📈 Прогресс до следующего уровня: {progress_percent}%\n"
        )

        await message.answer(stats_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error showing stats: {e}", exc_info=True)
        await message.answer("❌ Ошибка при получении статистики. Попробуйте /profile", parse_mode="HTML")


@router.message(F.text == "🖼 Галерея")
async def button_gallery(message: Message, db_session):
    """Кнопка — показ галереи."""
    from handlers.mission import cmd_gallery
    await cmd_gallery(message, db_session)


@router.message(F.text == "ℹ️ Помощь")
async def button_help(message: Message):
    """Кнопка — помощь."""
    await cmd_help(message)