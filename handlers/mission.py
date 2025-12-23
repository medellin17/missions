#/handlers/mission.py
"""
Основные handler'ы для работы с миссиями: 
- Получение миссии
- Отправка отчета
- Оценка миссии
- Галерея выполненных миссий
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models. completion import Completion
from models. mission import Mission
from models.user import User
from services.user_service import UserService
from services.mission_service import MissionService
from services.completion_service import CompletionService
from keyboards.mission_kb import get_difficulty_keyboard, get_mission_keyboard
from core.exceptions import NoChargesLeft, MissionNotFound

router = Router()
logger = logging.getLogger(__name__)


class MissionState(StatesGroup):
    """FSM состояния для работы с миссиями"""
    waiting_for_report = State()
    waiting_for_rating = State()


@router.message(Command("mission"))
async def cmd_mission(message: Message, db_session:  AsyncSession, state: FSMContext) -> None:
    """
    Команда /mission — получить новую миссию.
    
    Args:
        message: Telegram сообщение
        db_session: Сессия БД
        state: FSM контекст
    """
    try:
        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(message.from_user.id)
        user = await user_service. check_and_reset_charges(user)

        # Проверка на блокировку
        if getattr(user, "is_banned", False):
            await message. answer("🚫 Доступ ограничен:  вы заблокированы.")
            return

        # Проверка зарядов
        if user. charges <= 0:
            raise NoChargesLeft(user. user_id)

        await state.clear()

        # Получаем случайную миссию
        mission_service = MissionService(db_session)
        mission = await mission_service.get_random_mission(user. level)

        if not mission: 
            await message.answer(
                "😢 <b>Не удалось найти миссию. </b>\n\n"
                "Попробуйте позже или свяжитесь с администратором.",
                parse_mode="HTML"
            )
            return

        # Сохраняем в state
        await state.update_data(mission_id=mission.id, mission_text=mission.text)
        await state.set_state(MissionState.waiting_for_report)

        # Формируем текст миссии
        difficulty_emoji = {
            "easy": "🟢",
            "medium": "🟡",
            "hard":  "🔴",
        }
        emoji = difficulty_emoji. get(mission.difficulty, "🎯")

        text = (
            f"🎯 <b>Миссия #{mission.id}</b>\n\n"
            f"<b>{mission.text}</b>\n\n"
            f"{emoji} <i>Сложность: {mission.difficulty}</i>\n"
            f"⭐ <i>Награда: {mission.points_reward} очков</i>\n\n"
            f"<b>Как отчитаться:</b>\n"
            "1. Выполните миссию\n"
            "2. Напишите сюда описание или отправьте фото\n"
            "3. Получите очки и опыт!"
        )

        await message.answer(text, parse_mode="HTML")

        # Применяем заряд
        await user_service.consume_charge(user)
        await db_session.commit()

    except NoChargesLeft: 
        await message.answer(
            "⚡ <b>У вас закончились заряды!</b>\n\n"
            "💡 Они восстановятся автоматически в 00:00 по МСК.\n"
            "Поделитесь своими идеями в /help или ждите следующего дня! ",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in cmd_mission: {e}", exc_info=True)
        await message.answer("❌ Ошибка при получении миссии.")


@router.message(MissionState.waiting_for_report)
async def report_mission(
    message: Message,
    db_session: AsyncSession,
    state: FSMContext
) -> None:
    """
    Обработка отчета о выполнении миссии (текст или фото).
    """
    try:
        data = await state.get_data()
        mission_id = data. get("mission_id")

        if not mission_id: 
            await message.answer("❌ Ошибка: миссия не найдена в памяти.")
            await state.clear()
            return

        # Получаем миссию
        result = await db_session.execute(
            select(Mission).where(Mission.id == mission_id)
        )
        mission = result.scalar_one_or_none()

        if not mission:
            raise MissionNotFound(mission_id)

        # Определяем тип отчета
        report_type = "text"
        report_content = message.text or ""

        if message.photo:
            report_type = "photo"
            report_content = message.photo[-1].file_id  # Берем самое большое фото

        # Создаем запись о выполнении
        completion_service = CompletionService(db_session)
        completion = await completion_service.create_completion(
            user_id=message. from_user.id,
            mission_id=mission_id,
            report_type=report_type,
            report_content=report_content,
            points_reward=mission.points_reward,
        )

        # Добавляем очки пользователю
        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(message.from_user. id)
        await user_service.add_points(user, mission.points_reward)
        await db_session.commit()

        # Просим оценить миссию
        await state.set_state(MissionState.waiting_for_rating)
        await state.update_data(completion_id=completion.id)

        response_text = (
            f"✅ <b>Отчет принят!</b>\n\n"
            f"🎉 +{mission.points_reward} очков\n\n"
            f"<b>Как тебе миссия? </b>"
        )

        # Кнопки оценки (1-5 звезд)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="1️⃣", callback_data="rate: 1"),
                    InlineKeyboardButton(text="2️⃣", callback_data="rate:2"),
                    InlineKeyboardButton(text="3️⃣", callback_data="rate:3"),
                    InlineKeyboardButton(text="4️⃣", callback_data="rate:4"),
                    InlineKeyboardButton(text="5️⃣", callback_data="rate:5"),
                ]
            ]
        )

        await message.answer(response_text, parse_mode="HTML", reply_markup=keyboard)

    except MissionNotFound as e:
        logger.error(f"Mission not found: {e}")
        await message.answer("❌ Миссия удалена.  Получите новую:  /mission")
        await state.clear()
    except Exception as e:
        logger. error(f"Error in report_mission: {e}", exc_info=True)
        await message. answer("❌ Ошибка при обработке отчета.")
        await state.clear()


@router.callback_query(F.data. startswith("rate:"))
async def rate_mission(callback:  CallbackQuery, db_session: AsyncSession, state: FSMContext) -> None:
    """
    Обработка оценки миссии (1-5).
    """
    try: 
        rating = int(callback.data.split(":")[1])
        data = await state.get_data()
        completion_id = data.get("completion_id")

        if not completion_id:
            await callback. answer("❌ Ошибка: выполнение не найдено.")
            return

        # Обновляем оценку в БД
        result = await db_session.execute(
            select(Completion).where(Completion.id == completion_id)
        )
        completion = result.scalar_one_or_none()

        if completion:
            completion.rating = rating  # Предполагаем, что поле rating существует
            await db_session. commit()

        ratings_text = {
            1: "😢 Не очень.. .",
            2: "😕 Нормально",
            3: "😐 Средненько",
            4: "😊 Хорошо! ",
            5: "🤩 Отлично!",
        }

        await callback.message.edit_text(
            f"✅ <b>Спасибо за оценку! </b>\n\n"
            f"{ratings_text. get(rating, '')}\n\n"
            f"Ваш отзыв помогает улучшать качество миссий.",
            parse_mode="HTML"
        )

        await state.clear()
        await callback.answer()

    except Exception as e: 
        logger.error(f"Error in rate_mission: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при обработке оценки.", show_alert=True)


@router.message(Command("gallery"))
@router.message(F.text == "🖼 Галерея")
async def cmd_gallery(message: Message, db_session: AsyncSession) -> None:
    """
    Команда /gallery — показать все выполненные миссии. 
    """
    try:
        # Получаем все выполнения пользователя
        result = await db_session.execute(
            select(Completion)
            .where(Completion. telegram_user_id == message. from_user.id)
            .order_by(desc(Completion.completed_at))
            .limit(10)
        )
        completions = result.scalars().all()

        if not completions: 
            await message.answer(
                "🖼 <b>Ваша галерея пуста</b>\n\n"
                "Выполните несколько миссий, чтобы они появились здесь!\n"
                "Начните с /mission",
                parse_mode="HTML"
            )
            return

        # Формируем сообщение
        text = f"🖼 <b>Ваша галерея</b> ({len(completions)} выполнено)\n\n"

        for i, completion in enumerate(completions[: 5], 1):
            date_str = completion.completed_at.strftime("%d. %m.%Y %H:%M") if completion.completed_at else "—"
            rating_str = "⭐" * (completion.rating or 0) if hasattr(completion, "rating") else ""

            text += (
                f"{i}. {date_str}\n"
                f"   Награда: +{completion.points_reward} очков {rating_str}\n"
            )

        if len(completions) > 5:
            text += f"\n... и ещё {len(completions) - 5} миссий"

        await message. answer(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in cmd_gallery: {e}", exc_info=True)
        await message.answer("❌ Ошибка при открытии галереи.")


@router.message(Command("done"))
async def cmd_done(message: Message, db_session: AsyncSession, state: FSMContext) -> None:
    """
    Команда /done — быстрый отчет о выполнении. 
    Использование: /done [текст отчета]
    """
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "📝 <b>Использование:</b>\n"
            "<code>/done [описание выполненного]</code>\n\n"
            "Пример:\n"
            "<code>/done Сфотографировал 3 интересных предмета на улице</code>",
            parse_mode="HTML"
        )
        return

    report_text = args[1]

    try:
        # Проверяем, есть ли активная миссия в state
        data = await state.get_data()
        mission_id = data.get("mission_id")

        if not mission_id: 
            await message.answer("❌ Сначала получите миссию через /mission")
            return

        # Создаем отчет (переиспользуем логику из report_mission)
        message. text = report_text
        await report_mission(message, db_session, state)

    except Exception as e:
        logger.error(f"Error in cmd_done: {e}", exc_info=True)
        await message.answer("❌ Ошибка при обработке отчета.")