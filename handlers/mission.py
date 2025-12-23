# handlers/mission.py

from __future__ import annotations

import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from sqlalchemy import desc, func, select

from models.completion import Completion
from models.mission import Mission
from models.user import User

# --- services imports (поддержка разных имён модулей) ---
try:
    from services.user_service import UserService
except Exception:  # pragma: no cover
    from services.userservice import UserService  # type: ignore

try:
    from services.analytics_service import AnalyticsService
except Exception:  # pragma: no cover
    from services.analyticsservice import AnalyticsService  # type: ignore

# --- keyboards imports (поддержка разных имён модулей) ---
try:
    from keyboards.mission_kb import get_difficulty_keyboard, get_mission_keyboard
except Exception:  # pragma: no cover
    from keyboards.missionkb import getdifficultykeyboard as get_difficulty_keyboard  # type: ignore
    from keyboards.missionkb import getmissionkeyboard as get_mission_keyboard  # type: ignore


router = Router()
logger = logging.getLogger(__name__)


class MissionStates(StatesGroup):
    waiting_for_difficulty = State()
    has_current_mission = State()
    waiting_for_report = State()


def _format_tags(tags_list: str | None) -> str:
    if not tags_list:
        return ""
    tags = [t.strip() for t in tags_list.split(",") if t.strip()]
    if not tags:
        return ""
    return ", ".join(tags[:3])


def _calc_level(points: int) -> int:
    level = points // 100 + 1
    if level < 1:
        level = 1
    if level > 3:
        level = 3
    return level


def _difficulty_from_callback(data: str) -> str | None:
    # поддержка двух форматов (если клавиатура в проекте где-то отличается)
    if data in ("difficulty_basic", "difficultybasic"):
        return "basic"
    if data in ("difficulty_elite", "difficultyelite"):
        return "elite"
    return None


# =============================================================================
# /mission
# =============================================================================
@router.message(Command("mission"))
async def cmd_mission(message: Message, db_session, state: FSMContext):
    try:
        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(message.from_user.id)
        user = await user_service.check_and_reset_charges(user)

        if getattr(user, "is_banned", False):
            await message.answer("🚫 Доступ ограничен: вы заблокированы.", parse_mode="HTML")
            return

        if user.charges <= 0:
            await message.answer(
                "⚡ У вас закончились заряды. Они восстановятся автоматически (раз в сутки).",
                parse_mode="HTML",
            )
            return

        await state.clear()
        text = (
            "🎯 <b>Выбор миссии</b>\n\n"
            f"⚡ Заряды: <b>{user.charges}</b>/3\n"
            f"⭐ Очки: <b>{user.points}</b>\n"
            f"🏅 Уровень: <b>{user.level}</b>\n\n"
            "Выберите сложность:"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=get_difficulty_keyboard())
        await state.set_state(MissionStates.waiting_for_difficulty)

    except Exception as e:
        logger.error(f"Error in cmd_mission: {e}", exc_info=True)
        await state.clear()
        await message.answer("❌ Ошибка. Попробуйте ещё раз: /mission", parse_mode="HTML")


# =============================================================================
# Difficulty callbacks
# =============================================================================
@router.callback_query(F.data.in_({"difficulty_basic", "difficulty_elite", "difficultybasic", "difficultyelite"}))
async def callback_difficulty(callback: CallbackQuery, state: FSMContext, db_session):
    try:
        difficulty = _difficulty_from_callback(callback.data or "")
        if not difficulty:
            await callback.answer("❌ Неизвестная сложность", show_alert=True)
            return

        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(callback.from_user.id)
        user = await user_service.check_and_reset_charges(user)

        if getattr(user, "is_banned", False):
            await callback.answer("🚫 Доступ ограничен", show_alert=True)
            await state.clear()
            return

        if user.charges <= 0:
            await callback.message.edit_text(
                "⚡ У вас закончились заряды. Они восстановятся автоматически (раз в сутки).",
                parse_mode="HTML",
            )
            await callback.answer()
            await state.clear()
            return

        mission_result = await db_session.execute(
            select(Mission)
            .where(
                Mission.active.is_(True),
                Mission.is_archived.is_(False),
                Mission.difficulty == difficulty,
            )
            .order_by(func.random())
            .limit(1)
        )
        mission = mission_result.scalar_one_or_none()

        if not mission:
            await callback.message.edit_text(
                "😕 Не нашлось активных миссий этой сложности.",
                parse_mode="HTML",
            )
            await callback.answer()
            await state.clear()
            return

        await state.update_data(current_mission_id=mission.id, charge_consumed=False)
        await state.set_state(MissionStates.has_current_mission)

        tags_text = _format_tags(getattr(mission, "tags_list", None))
        points_emoji = "💎" if difficulty == "elite" else "⭐"

        text = (
            f"📝 <b>Миссия</b>\n\n"
            f"{mission.text}\n\n"
            f"{points_emoji} Награда: <b>{int(mission.points_reward or 0)}</b>\n"
            f"⚙️ Сложность: <b>{difficulty.upper()}</b>\n"
        )
        if tags_text:
            text += f"🏷 Теги: <i>{tags_text}</i>\n"
        text += f"\n⚡ Заряды: <b>{user.charges}</b>/3"

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_mission_keyboard())

        # analytics (не ломаем флоу, если аналитика падает)
        try:
            analytics = AnalyticsService(db_session)
            await analytics.log_user_activity(
                user.user_id,
                "mission_viewed",
                {"mission_id": mission.id, "difficulty": difficulty},
            )
        except Exception:
            pass

        await callback.answer()

    except Exception as e:
        logger.error(f"Error in callback_difficulty: {e}", exc_info=True)
        await callback.message.edit_text("❌ Ошибка. Попробуйте снова: /mission", parse_mode="HTML")
        await callback.answer()
        await state.clear()


# =============================================================================
# Cancel current mission view
# =============================================================================
@router.callback_query(F.data == "mission_cancel")
async def callback_mission_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("✅ Отменено. Используйте /mission чтобы начать заново.", parse_mode="HTML")
    await callback.answer()


# =============================================================================
# Done -> ask report (consume charge once)
# =============================================================================
@router.callback_query(F.data == "mission_done")
async def callback_mission_done(callback: CallbackQuery, state: FSMContext, db_session):
    try:
        data = await state.get_data()
        mission_id = data.get("current_mission_id")
        charge_consumed = data.get("charge_consumed", False)

        if not mission_id:
            await callback.answer("❌ Нет активной миссии. Используйте /mission", show_alert=True)
            await state.clear()
            return

        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(callback.from_user.id)
        user = await user_service.check_and_reset_charges(user)

        if getattr(user, "is_banned", False):
            await callback.answer("🚫 Доступ ограничен", show_alert=True)
            await state.clear()
            return

        if not charge_consumed:
            ok = await user_service.consume_charge(user)
            if not ok:
                await callback.answer("⚡ Заряды закончились. Попробуйте позже.", show_alert=True)
                await state.clear()
                return
            await state.update_data(charge_consumed=True)

        # проверим миссию существует
        mission_result = await db_session.execute(select(Mission).where(Mission.id == int(mission_id)))
        mission = mission_result.scalar_one_or_none()
        if not mission:
            await callback.answer("❌ Миссия не найдена", show_alert=True)
            await state.clear()
            return

        await state.update_data(mission_id=mission.id)
        await state.set_state(MissionStates.waiting_for_report)

        await callback.message.answer(
            "✅ Отлично! Теперь пришлите отчёт:\n\n"
            "• Текстом и/или фото\n"
            "• Для отмены напишите: <code>cancel</code>",
            parse_mode="HTML",
        )

        try:
            analytics = AnalyticsService(db_session)
            await analytics.log_user_activity(user.user_id, "mission_started", {"mission_id": mission.id})
        except Exception:
            pass

        await callback.answer("✅ Ожидаю отчёт")

    except Exception as e:
        logger.error(f"Error in callback_mission_done: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)
        await state.clear()


# =============================================================================
# Skip mission
# =============================================================================
@router.callback_query(F.data == "mission_skip")
async def callback_mission_skip(callback: CallbackQuery, state: FSMContext, db_session):
    try:
        data = await state.get_data()
        charge_consumed = data.get("charge_consumed", False)

        await state.clear()
        await callback.message.edit_text(
            "⏭ Миссия пропущена.\n\nИспользуйте /mission чтобы получить новую.",
            parse_mode="HTML",
        )

        try:
            user_service = UserService(db_session)
            user = await user_service.get_or_create_user(callback.from_user.id)
            analytics = AnalyticsService(db_session)
            await analytics.log_user_activity(
                user.user_id,
                "mission_skipped",
                {"charge_consumed": charge_consumed},
            )
        except Exception:
            pass

        await callback.answer()

    except Exception as e:
        logger.error(f"Error in callback_mission_skip: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)
        await state.clear()


# =============================================================================
# Help
# =============================================================================
@router.callback_query(F.data == "mission_help")
async def callback_mission_help(callback: CallbackQuery):
    help_text = (
        "ℹ️ <b>Как проходить миссии</b>\n\n"
        "1) /mission — получить миссию\n"
        "2) Выбрать сложность\n"
        "3) Выполнить задание\n"
        "4) Нажать «✅ Выполнить миссию»\n"
        "5) Отправить отчёт текстом и/или фото\n\n"
        "Команды:\n"
        "• /profile — профиль\n"
        "• /gallery — галерея\n"
        "• /cancel — отмена текущего шага"
    )
    await callback.message.answer(help_text, parse_mode="HTML")
    await callback.answer()


# =============================================================================
# REPORT
# =============================================================================
@router.message(MissionStates.waiting_for_report)
async def process_mission_report(message: Message, state: FSMContext, db_session):
    try:
        if message.text and message.text.strip().lower() == "cancel":
            await state.clear()
            await message.answer("✅ Отмена. Используйте /mission чтобы начать заново.", parse_mode="HTML")
            return

        data = await state.get_data()
        mission_id = data.get("mission_id")

        if not mission_id:
            await state.clear()
            await message.answer("❌ Не найдена активная миссия. Используйте /mission.", parse_mode="HTML")
            return

        report_type: str | None = None
        report_text: str | None = None
        report_file_id: str | None = None

        if message.photo:
            report_file_id = message.photo[-1].file_id
            report_text = (message.caption or "").strip() or None
            report_type = "both" if report_text else "photo"
        elif message.text:
            report_text = message.text.strip()
            report_type = "text"
        else:
            await message.answer("❌ Пришлите текст и/или фото. Для отмены: cancel", parse_mode="HTML")
            return

        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(message.from_user.id)

        if getattr(user, "is_banned", False):
            await state.clear()
            await message.answer("🚫 Доступ ограничен: вы заблокированы.", parse_mode="HTML")
            return

        mission_result = await db_session.execute(select(Mission).where(Mission.id == int(mission_id)))
        mission = mission_result.scalar_one_or_none()
        if not mission:
            await state.clear()
            await message.answer("❌ Миссия не найдена. Используйте /mission.", parse_mode="HTML")
            return

        # ВАЖНО:
        # Completion.user_id -> users.id (PK), а не telegram id (User.user_id)
        completion = Completion(
            user_id=user.id,
            mission_id=mission.id,
            report_type=report_type,
            report_text=report_text,
            report_file_id=report_file_id,
            points_reward=int(mission.points_reward or 0),
            completed_at=datetime.utcnow(),
        )
        db_session.add(completion)

        old_level = int(user.level or 1)
        gained = int(mission.points_reward or 0)
        user.points = int(user.points or 0) + gained
        user.level = _calc_level(user.points)

        await db_session.commit()

        level_up_text = ""
        if user.level > old_level:
            level_up_text = f"\n\n🎉 Новый уровень: <b>{user.level}</b>"

        photo_emoji = "📷" if report_file_id else "📝"
        await state.clear()

        await message.answer(
            f"✅ Отчёт принят! {photo_emoji}\n\n"
            f"⭐ Начислено: <b>{gained}</b>\n"
            f"🏅 Уровень: <b>{user.level}</b>\n"
            f"💰 Очки: <b>{user.points}</b>\n"
            f"{level_up_text}\n\n"
            "Можно посмотреть отчёты: /gallery\n"
            "Новая миссия: /mission",
            parse_mode="HTML",
        )

        try:
            analytics = AnalyticsService(db_session)
            await analytics.log_user_activity(
                user.user_id,
                "mission_completed",
                {"mission_id": mission.id, "points": gained, "report_type": report_type},
            )
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Error processing mission report: {e}", exc_info=True)
        await state.clear()
        await message.answer("❌ Ошибка при сохранении отчёта. Попробуйте ещё раз: /mission", parse_mode="HTML")


# =============================================================================
# /gallery
# =============================================================================
@router.message(Command("gallery"))
async def cmd_gallery(message: Message, db_session):
    try:
        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(message.from_user.id)

        result = await db_session.execute(
            select(Completion)
            .where(Completion.user_id == user.id)
            .order_by(desc(Completion.completed_at))
            .limit(10)
        )
        completions = result.scalars().all()

        if not completions:
            await message.answer("🖼 Галерея пуста. Выполните миссию через /mission.", parse_mode="HTML")
            return

        photos_sent = 0
        text_reports: list[str] = []

        for c in completions:
            dt = c.completed_at.strftime("%d.%m.%Y %H:%M") if c.completed_at else "—"
            points = int(c.points_reward or 0)

            if c.report_file_id:
                caption = f"📌 {dt} • ⭐ {points}"
                if c.report_text:
                    caption += f"\n\n{c.report_text[:700]}"
                try:
                    await message.answer_photo(photo=c.report_file_id, caption=caption)
                    photos_sent += 1
                    if photos_sent >= 5:
                        break
                except Exception:
                    # если фото не отправилось — покажем как текст
                    text_reports.append(f"📌 {dt} • ⭐ {points}\n{(c.report_text or 'Фото-отчёт').strip()[:300]}")
            else:
                if c.report_text:
                    text_reports.append(f"📌 {dt} • ⭐ {points}\n{c.report_text.strip()[:300]}")

        if text_reports and photos_sent < 5:
            await message.answer("\n\n---\n\n".join(text_reports[: (5 - photos_sent)]), parse_mode="HTML")

        if photos_sent == 0 and not text_reports:
            await message.answer("🖼 В отчётах нет текста/фото для показа.", parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in cmd_gallery: {e}", exc_info=True)
        await message.answer("❌ Ошибка при открытии галереи.", parse_mode="HTML")


# =============================================================================
# /profile
# =============================================================================
@router.message(Command("profile"))
async def cmd_profile(message: Message, db_session):
    try:
        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(message.from_user.id)
        user = await user_service.check_and_reset_charges(user)

        if getattr(user, "is_banned", False):
            await message.answer("🚫 Доступ ограничен: вы заблокированы.", parse_mode="HTML")
            return

        result = await db_session.execute(
            select(func.count(Completion.id)).where(Completion.user_id == user.id)
        )
        total_completed = int(result.scalar_one_or_none() or 0)

        next_level_points = 100
        current_score = int(user.points or 0) % next_level_points
        progress_percent = int((current_score / next_level_points) * 100) if user.level < 3 else 100

        filled = min(10, max(0, progress_percent // 10))
        progress_bar = "█" * filled + "░" * (10 - filled)

        display_name = user.username if user.username else str(user.user_id)
        name_hint = "" if user.username else "\n\n✏️ Установить ник: <code>/setname JohnDoe</code>"

        profile_text = (
            "👤 <b>Профиль</b>\n\n"
            f"🆔 <code>{display_name}</code>\n"
            f"🏅 Уровень: <b>{user.level}</b>\n"
            f"⭐ Очки: <b>{user.points}</b>\n"
            f"⚡ Заряды: <b>{user.charges}</b>/3\n"
            f"✅ Выполнено миссий: <b>{total_completed}</b>\n\n"
            f"📈 Прогресс уровня:\n<code>{progress_bar}</code> {progress_percent}%"
            f"{name_hint}"
        )
        await message.answer(profile_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in cmd_profile: {e}", exc_info=True)
        await message.answer("❌ Ошибка при показе профиля.", parse_mode="HTML")


# =============================================================================
# /setname
# =============================================================================
@router.message(Command("setname"))
async def cmd_setname(message: Message, db_session):
    try:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            await message.answer(
                "✏️ <b>Установка никнейма</b>\n\n"
                "<code>/setname JohnDoe</code>\n\n"
                "Требования:\n"
                "• 3–20 символов\n"
                "• Только буквы, цифры и _\n"
                "• Никнейм должен быть уникальным",
                parse_mode="HTML",
            )
            return

        username = parts[1].strip()
        if len(username) < 3 or len(username) > 20:
            await message.answer("❌ Никнейм должен содержать от 3 до 20 символов.", parse_mode="HTML")
            return

        if not username.replace("_", "").isalnum():
            await message.answer("❌ Никнейм может содержать только буквы, цифры и символ _", parse_mode="HTML")
            return

        existing = await db_session.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            await message.answer("❌ Этот никнейм уже занят. Попробуйте другой.", parse_mode="HTML")
            return

        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(message.from_user.id)

        user.username = username
        await db_session.commit()

        await message.answer(f"✅ Никнейм установлен: <b>{username}</b>", parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in cmd_setname: {e}", exc_info=True)
        await message.answer("❌ Ошибка при установке никнейма.", parse_mode="HTML")


# =============================================================================
# /cancel (FSM)
# =============================================================================
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("ℹ️ Нечего отменять. Используйте /mission.", parse_mode="HTML")
        return

    await state.clear()
    await message.answer("✅ Отменено. Используйте /mission чтобы начать заново.", parse_mode="HTML")