# handlers/admin_analytics.py

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from sqlalchemy import select, func, desc, and_

from core.config import settings

from keyboards.admin_kb import (
    get_admin_menu_keyboard,
    get_analytics_menu_keyboard,
    get_user_management_keyboard,
    get_user_list_keyboard,
    get_user_action_keyboard,
    get_group_management_keyboard,
)

from models.user import User
from models.mission import Mission
from models.completion import Completion

# MissionGroup может называться по-разному в разных ветках проекта
try:
    from models.mission_group import MissionGroup, GroupType  # type: ignore
except Exception:
    try:
        from models.missiongroup import MissionGroup, GroupType  # type: ignore
    except Exception:
        MissionGroup = None  # type: ignore
        GroupType = None  # type: ignore


router = Router()
logger = logging.getLogger(__name__)

# =============================================================================
# Helpers: admin check + model field compatibility
# =============================================================================

def is_admin(user_id: int) -> bool:
    admin_ids = getattr(settings, "ADMIN_IDS", None) or getattr(settings, "ADMINIDS", None) or []
    return user_id in admin_ids


def _safe_split(text: str, limit: int = 3800) -> List[str]:
    if not text:
        return [""]
    parts: List[str] = []
    chunk = ""
    for line in text.splitlines(True):
        if len(chunk) + len(line) > limit:
            parts.append(chunk)
            chunk = ""
        chunk += line
    if chunk:
        parts.append(chunk)
    return parts


def _user_id_col():
    if hasattr(User, "user_id"):
        return User.user_id
    return User.userid


def _user_username_col():
    if hasattr(User, "username"):
        return User.username
    # fallback (на случай старой схемы)
    return User.userid


def _user_is_banned_col():
    if hasattr(User, "is_banned"):
        return User.is_banned
    if hasattr(User, "isbanned"):
        return User.isbanned
    # fallback: считаем, что банов нет
    return None


def _user_created_at_col():
    if hasattr(User, "created_at"):
        return User.created_at
    if hasattr(User, "createdat"):
        return User.createdat
    return None


def _user_charges_attr(u: User) -> int:
    return int(getattr(u, "charges", 0) or 0)


def _user_points_attr(u: User) -> int:
    return int(getattr(u, "points", 0) or 0)


def _user_level_attr(u: User) -> int:
    return int(getattr(u, "level", 1) or 1)


def _user_id_attr(u: User) -> int:
    return int(getattr(u, "user_id", getattr(u, "userid", 0)) or 0)


def _user_is_banned_attr(u: User) -> bool:
    if hasattr(u, "is_banned"):
        return bool(getattr(u, "is_banned") or False)
    if hasattr(u, "isbanned"):
        return bool(getattr(u, "isbanned") or False)
    return False


def _user_created_at_attr(u: User) -> Optional[datetime]:
    return getattr(u, "created_at", getattr(u, "createdat", None))


def _mission_points_col():
    if hasattr(Mission, "points_reward"):
        return Mission.points_reward
    return Mission.pointsreward


def _mission_is_archived_col():
    if hasattr(Mission, "is_archived"):
        return Mission.is_archived
    return Mission.isarchived


def _mission_created_at_col():
    if hasattr(Mission, "created_at"):
        return Mission.created_at
    return Mission.createdat


def _mission_group_id_col():
    if hasattr(Mission, "group_id"):
        return Mission.group_id
    return Mission.groupid


def _mission_is_group_mission_col():
    if hasattr(Mission, "is_group_mission"):
        return Mission.is_group_mission
    return Mission.isgroupmission


def _mission_sequence_order_col():
    if hasattr(Mission, "sequence_order"):
        return Mission.sequence_order
    return Mission.sequenceorder


def _completion_user_col():
    # цель: единый стандарт telegram_user_id
    if hasattr(Completion, "telegram_user_id"):
        return Completion.telegram_user_id
    if hasattr(Completion, "userid"):
        return Completion.userid
    if hasattr(Completion, "user_id"):
        return Completion.user_id
    raise AttributeError("Completion: no telegram_user_id/userid/user_id column")


def _completion_completed_at_col():
    if hasattr(Completion, "completed_at"):
        return Completion.completed_at
    if hasattr(Completion, "completedat"):
        return Completion.completedat
    return None


# =============================================================================
# Difficulty normalization (быстро и безопасно)
# =============================================================================

ALLOWED_DIFFICULTIES = {"basic", "elite"}
DIFFICULTY_LABEL = {"basic": "Basic", "elite": "Elite"}
DEFAULT_POINTS = {"basic": 10, "elite": 20}


def normalize_difficulty(raw: str) -> str:
    v = (raw or "").strip().lower()
    if v not in ALLOWED_DIFFICULTIES:
        raise ValueError("Invalid difficulty")
    return v


def parse_tags(raw: str) -> List[str]:
    s = (raw or "").strip()
    if not s or s in {"-", "—"}:
        return []
    tags = [t.strip() for t in s.split(",")]
    return [t for t in tags if t]


def get_tags(m: Mission) -> List[str]:
    # поддержка разных реализаций (m.tags list vs m.tagslist string)
    if hasattr(m, "tags") and getattr(m, "tags"):
        return list(getattr(m, "tags") or [])
    raw = getattr(m, "tagslist", "")
    return parse_tags(raw)


def set_tags(m: Mission, tags: List[str]) -> None:
    if hasattr(m, "tagslist"):
        m.tagslist = ", ".join(tags) if tags else ""
    if hasattr(m, "tags"):
        m.tags = tags


# =============================================================================
# Admin FSM
# =============================================================================

class AdminStates(StatesGroup):
    waiting_for_user_search = State()
    waiting_for_points_amount = State()

    # Missions UI
    mission_create_text = State()
    mission_create_tags = State()
    mission_create_difficulty = State()
    mission_create_points = State()

    mission_find_id = State()
    mission_edit_value = State()


# =============================================================================
# Admin entry
# =============================================================================

@router.message(Command("admin"))
async def cmd_admin(message: Message, db_session):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён", parse_mode="HTML")
        return

    await message.answer(
        "⚙️ <b>Админ-панель</b>",
        parse_mode="HTML",
        reply_markup=get_admin_menu_keyboard(),
    )


@router.callback_query(F.data == "admin")
async def cb_admin(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    await callback.message.edit_text(
        "⚙️ <b>Админ-панель</b>",
        parse_mode="HTML",
        reply_markup=get_admin_menu_keyboard(),
    )
    await callback.answer()


# =============================================================================
# Analytics (простая, без внешних сервисов)
# =============================================================================

async def _get_user_growth(db_session) -> Dict[str, int]:
    created_col = _user_created_at_col()
    total = (await db_session.execute(select(func.count(User.id)))).scalar_one() or 0

    today = 0
    week = 0
    if created_col is not None:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = datetime.utcnow() - timedelta(days=7)
        today = (await db_session.execute(select(func.count(User.id)).where(created_col >= today_start))).scalar_one() or 0
        week = (await db_session.execute(select(func.count(User.id)).where(created_col >= week_start))).scalar_one() or 0

    return {"total": int(total), "new_today": int(today), "new_week": int(week)}


async def _get_mission_completion_stats(db_session, days: int = 30) -> Dict[str, Any]:
    completed_col = _completion_completed_at_col()
    user_col = _completion_user_col()

    total_missions = (await db_session.execute(select(func.count(Mission.id)))).scalar_one() or 0
    active_missions = (await db_session.execute(select(func.count(Mission.id)).where(Mission.active.is_(True)))).scalar_one() or 0

    completions_total = (await db_session.execute(select(func.count(Completion.id)))).scalar_one() or 0
    unique_users = (await db_session.execute(select(func.count(func.distinct(user_col))))).scalar_one() or 0

    completions_period = completions_total
    if completed_col is not None:
        since = datetime.utcnow() - timedelta(days=days)
        completions_period = (
            (await db_session.execute(select(func.count(Completion.id)).where(completed_col >= since))).scalar_one() or 0
        )

    return {
        "total_missions": int(total_missions),
        "active_missions": int(active_missions),
        "completions_total": int(completions_total),
        "completions_period": int(completions_period),
        "unique_users": int(unique_users),
    }


@router.callback_query(F.data == "admin_analytics")
async def cb_admin_analytics(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    try:
        growth = await _get_user_growth(db_session)
        mstats = await _get_mission_completion_stats(db_session, days=30)

        text = (
            "📊 <b>Общая аналитика</b>\n\n"
            f"👥 Пользователи: <b>{growth['total']}</b>\n"
            f"➕ Новых сегодня: <b>{growth['new_today']}</b>\n"
            f"➕ Новых за 7 дней: <b>{growth['new_week']}</b>\n\n"
            f"🎯 Миссий всего: <b>{mstats['total_missions']}</b>\n"
            f"✅ Активных: <b>{mstats['active_missions']}</b>\n"
            f"✅ Выполнений всего: <b>{mstats['completions_total']}</b>\n"
            f"✅ Выполнений за 30 дней: <b>{mstats['completions_period']}</b>\n"
            f"👤 Уникальных пользователей в completion: <b>{mstats['unique_users']}</b>\n"
        )

        await callback.message.answer(text, parse_mode="HTML", reply_markup=get_analytics_menu_keyboard())
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_analytics error: {e}", exc_info=True)
        await callback.message.answer("❌ Ошибка при формировании аналитики.", parse_mode="HTML")
        await callback.answer()


@router.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    try:
        growth = await _get_user_growth(db_session)
        text = (
            "👥 <b>Пользователи</b>\n\n"
            f"Всего: <b>{growth['total']}</b>\n"
            f"Новых сегодня: <b>{growth['new_today']}</b>\n"
            f"Новых за 7 дней: <b>{growth['new_week']}</b>\n"
        )
        await callback.message.answer(text, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_users error: {e}", exc_info=True)
        await callback.message.answer("❌ Ошибка при формировании статистики пользователей.", parse_mode="HTML")
        await callback.answer()


@router.callback_query(F.data == "admin_missions")
async def cb_admin_missions(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    try:
        mstats = await _get_mission_completion_stats(db_session, days=30)
        text = (
            "🎯 <b>Миссии</b>\n\n"
            f"Всего миссий: <b>{mstats['total_missions']}</b>\n"
            f"Активных: <b>{mstats['active_missions']}</b>\n"
            f"Выполнений всего: <b>{mstats['completions_total']}</b>\n"
            f"Выполнений за 30 дней: <b>{mstats['completions_period']}</b>\n"
        )
        await callback.message.answer(text, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_missions error: {e}", exc_info=True)
        await callback.message.answer("❌ Ошибка при формировании статистики миссий.", parse_mode="HTML")
        await callback.answer()


@router.callback_query(F.data == "admin_pairs")
async def cb_admin_pairs(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    # В твоей текущей задаче пары не трогаем — просто не ломаем кнопку
    await callback.message.answer("👫 Раздел пар: пока без доработок.", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_themes")
async def cb_admin_themes(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    await callback.message.answer("📅 Тематические недели: пока без доработок.", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_report")
async def cb_admin_report(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    try:
        growth = await _get_user_growth(db_session)
        mstats = await _get_mission_completion_stats(db_session, days=30)
        text = (
            "📈 <b>Полный отчёт</b>\n\n"
            f"Пользователи всего: <b>{growth['total']}</b>\n"
            f"Новых сегодня: <b>{growth['new_today']}</b>\n"
            f"Новых за 7 дней: <b>{growth['new_week']}</b>\n\n"
            f"Миссий всего: <b>{mstats['total_missions']}</b>\n"
            f"Активных миссий: <b>{mstats['active_missions']}</b>\n"
            f"Выполнений всего: <b>{mstats['completions_total']}</b>\n"
            f"Выполнений за 30 дней: <b>{mstats['completions_period']}</b>\n"
        )
        for part in _safe_split(text):
            await callback.message.answer(part, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_report error: {e}", exc_info=True)
        await callback.message.answer("❌ Ошибка при формировании отчёта.", parse_mode="HTML")
        await callback.answer()


@router.callback_query(F.data == "admin_top_users")
async def cb_admin_top_users(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    try:
        user_col = _completion_user_col()
        completed_col = _completion_completed_at_col()

        q = (
            select(user_col.label("uid"), func.count(Completion.id).label("cnt"))
            .group_by(user_col)
            .order_by(desc(func.count(Completion.id)))
            .limit(15)
        )
        rows = (await db_session.execute(q)).all()

        if not rows:
            await callback.message.answer("Пока нет данных по активности.", parse_mode="HTML")
            await callback.answer()
            return

        lines = ["🔝 <b>Топ пользователей по completions</b>\n"]
        for i, (uid, cnt) in enumerate(rows, start=1):
            lines.append(f"{i}. <code>{uid}</code> — <b>{cnt}</b>")
        await callback.message.answer("\n".join(lines), parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_top_users error: {e}", exc_info=True)
        await callback.message.answer("❌ Ошибка при получении топа.", parse_mode="HTML")
        await callback.answer()


# =============================================================================
# User management UI
# =============================================================================

@router.callback_query(F.data == "admin_manage_users")
async def cb_admin_manage_users(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    try:
        banned_col = _user_is_banned_col()
        created_col = _user_created_at_col()

        total_users = (await db_session.execute(select(func.count(User.id)))).scalar_one() or 0
        banned_users = 0
        if banned_col is not None:
            banned_users = (
                (await db_session.execute(select(func.count(User.id)).where(banned_col.is_(True)))).scalar_one() or 0
            )

        new_today = 0
        if created_col is not None:
            today = datetime.utcnow().date()
            new_today = (
                (await db_session.execute(select(func.count(User.id)).where(func.date(created_col) == today))).scalar_one()
                or 0
            )

        text = (
            "👤 <b>Управление пользователями</b>\n\n"
            f"Всего: <b>{int(total_users)}</b>\n"
            f"Новых сегодня: <b>{int(new_today)}</b>\n"
            f"Заблокированных: <b>{int(banned_users)}</b>\n"
        )
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_user_management_keyboard())
        await callback.answer()
    except Exception as e:
        logger.error(f"admin_manage_users error: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin_list_users:"))
async def cb_admin_list_users(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    try:
        page = int(callback.data.split(":")[1])
    except Exception:
        page = 0
    page = max(page, 0)

    page_size = 10
    offset = page * page_size

    total_users = (await db_session.execute(select(func.count(User.id)))).scalar_one() or 0
    total_pages = max(1, (int(total_users) + page_size - 1) // page_size)

    if page > total_pages - 1:
        page = total_pages - 1
        offset = page * page_size

    res = await db_session.execute(select(User).order_by(desc(_user_created_at_col() or User.id)).limit(page_size).offset(offset))
    users = res.scalars().all()

    lines = [f"👥 <b>Пользователи</b> (стр. {page+1}/{total_pages})\n"]
    for u in users:
        uid = _user_id_attr(u)
        name = u.username if getattr(u, "username", None) else f"ID {uid}"
        status = "🚫" if _user_is_banned_attr(u) else "✅"
        lines.append(f"{status} <b>{name}</b>")
        lines.append(f"<code>{uid}</code> | lvl {_user_level_attr(u)} | {_user_points_attr(u)} pts | ⚡{_user_charges_attr(u)}/3")
        lines.append(f"➡️ <code>admin_user:{uid}</code>")
        lines.append("")

    await callback.message.edit_text(
        "\n".join(lines).strip(),
        parse_mode="HTML",
        reply_markup=get_user_list_keyboard(page, total_pages, int(total_users)),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_find_user")
async def cb_admin_find_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminStates.waiting_for_user_search)
    await callback.message.answer(
        "🔍 Введите:\n\n• Telegram ID (например <code>123456789</code>)\n• Или username (например <code>john_doe</code>)\n\nОтмена: /cancel",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_user_search)
async def process_admin_user_search(message: Message, state: FSMContext, db_session):
    if not is_admin(message.from_user.id):
        return

    if message.text and message.text.strip().lower() in ("/cancel", "cancel", "отмена"):
        await state.clear()
        await message.answer("❌ Поиск отменён", parse_mode="HTML")
        return

    term = (message.text or "").strip()
    if not term:
        await message.answer("❌ Пустой запрос. Введите ID или username.", parse_mode="HTML")
        return

    try:
        if term.isdigit():
            q = select(User).where(_user_id_col() == int(term))
        else:
            q = select(User).where(_user_username_col() == term)

        user = (await db_session.execute(q)).scalar_one_or_none()
        if not user:
            await message.answer("❌ Пользователь не найден. Попробуйте ещё раз или /cancel.", parse_mode="HTML")
            return

        uid = _user_id_attr(user)
        status = "🚫 Заблокирован" if _user_is_banned_attr(user) else "✅ Активен"
        created = _user_created_at_attr(user)
        created_str = created.strftime("%d.%m.%Y %H:%M") if created else "—"

        user_col = _completion_user_col()
        total_completions = (
            (await db_session.execute(select(func.count(Completion.id)).where(user_col == uid))).scalar_one() or 0
        )

        text = (
            "👤 <b>Пользователь</b>\n\n"
            f"ID: <code>{uid}</code>\n"
            f"Статус: <b>{status}</b>\n"
            f"Уровень: <b>{_user_level_attr(user)}</b>\n"
            f"Очки: <b>{_user_points_attr(user)}</b>\n"
            f"Заряды: <b>{_user_charges_attr(user)}/3</b>\n"
            f"Выполнений: <b>{int(total_completions)}</b>\n"
            f"Создан: <b>{created_str}</b>\n"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=get_user_action_keyboard(uid, _user_is_banned_attr(user)))
        await state.clear()

    except Exception as e:
        logger.error(f"admin_find_user error: {e}", exc_info=True)
        await message.answer("❌ Ошибка при поиске пользователя.", parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_toggle_ban:"))
async def cb_admin_toggle_ban(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    uid = int(callback.data.split(":")[1])
    user = (await db_session.execute(select(User).where(_user_id_col() == uid))).scalar_one_or_none()
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    # toggle
    if hasattr(user, "is_banned"):
        user.is_banned = not bool(user.is_banned)
        is_banned_now = bool(user.is_banned)
    elif hasattr(user, "isbanned"):
        user.isbanned = not bool(user.isbanned)
        is_banned_now = bool(user.isbanned)
    else:
        await callback.answer("В модели нет поля бана", show_alert=True)
        return

    await db_session.commit()
    await callback.answer("Ок", show_alert=True)
    await callback.message.answer(
        f"Пользователь <code>{uid}</code>: {'🚫 заблокирован' if is_banned_now else '✅ разблокирован'}",
        parse_mode="HTML",
        reply_markup=get_user_action_keyboard(uid, is_banned_now),
    )


@router.callback_query(F.data.startswith("admin_reset_charges:"))
async def cb_admin_reset_charges(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    uid = int(callback.data.split(":")[1])
    user = (await db_session.execute(select(User).where(_user_id_col() == uid))).scalar_one_or_none()
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    user.charges = 3
    if hasattr(user, "last_charge_reset"):
        user.last_charge_reset = datetime.utcnow()
    if hasattr(user, "lastchargereset"):
        user.lastchargereset = datetime.utcnow()

    await db_session.commit()
    await callback.answer("Сброшено", show_alert=True)


# =============================================================================
# Groups (не ломаем кнопку)
# =============================================================================

@router.callback_query(F.data == "admin_manage_groups")
async def cb_admin_manage_groups(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    await callback.message.edit_text(
        "🎯 <b>Группы миссий</b>\n\nПока без доработок в этом шаге.",
        parse_mode="HTML",
        reply_markup=get_group_management_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_noop")
async def cb_admin_noop(callback: CallbackQuery):
    await callback.answer()


# =============================================================================
# Missions CRUD (кнопочный UI внутри этого файла)
# =============================================================================

def _missions_manage_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📃 Список миссий", callback_data="am_list:0:all")],
        [InlineKeyboardButton(text="➕ Создать миссию", callback_data="am_create")],
        [InlineKeyboardButton(text="🔎 Найти по ID", callback_data="am_find")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _missions_list_keyboard(page: int, flt: str, total_pages: int) -> InlineKeyboardMarkup:
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"am_list:{page-1}:{flt}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="admin_noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"am_list:{page+1}:{flt}"))

    buttons = [
        [
            InlineKeyboardButton(text="Все", callback_data="am_list:0:all"),
            InlineKeyboardButton(text="Активные", callback_data="am_list:0:active"),
            InlineKeyboardButton(text="Архив", callback_data="am_list:0:archived"),
        ],
        nav,
        [InlineKeyboardButton(text="⚙️ Меню", callback_data="admin_manage_missions")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _mission_card_keyboard(mission_id: int, is_active: bool, is_archived: bool) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✏️ Текст", callback_data=f"am_edit:text:{mission_id}"),
            InlineKeyboardButton(text="🏷 Теги", callback_data=f"am_edit:tags:{mission_id}"),
        ],
        [
            InlineKeyboardButton(text="🎚 Difficulty", callback_data=f"am_edit:difficulty:{mission_id}"),
            InlineKeyboardButton(text="🎯 Points", callback_data=f"am_edit:points:{mission_id}"),
        ],
        [
            InlineKeyboardButton(
                text=("🚫 Деактивировать" if is_active else "✅ Активировать"),
                callback_data=f"am_toggle:{mission_id}",
            ),
            InlineKeyboardButton(
                text=("♻️ Разархивировать" if is_archived else "🗄 Архивировать"),
                callback_data=f"am_archive:{mission_id}",
            ),
        ],
        [
            InlineKeyboardButton(text="📦 В группу / убрать", callback_data=f"am_edit:group:{mission_id}"),
            InlineKeyboardButton(text="↕️ Порядок (seq)", callback_data=f"am_edit:order:{mission_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"am_delete_confirm:{mission_id}"),
            InlineKeyboardButton(text="⬅️ К списку", callback_data="am_list:0:all"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _mission_delete_confirm_keyboard(mission_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"am_delete:{mission_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"am_view:{mission_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _mission_card_text(m: Mission) -> str:
    tags = get_tags(m)
    tags_txt = ", ".join(tags) if tags else "—"

    points = getattr(m, "points_reward", getattr(m, "pointsreward", 10))
    is_archived = bool(getattr(m, "is_archived", getattr(m, "isarchived", False)))
    group_id = getattr(m, "group_id", getattr(m, "groupid", None))
    seq = getattr(m, "sequence_order", getattr(m, "sequenceorder", None))

    diff = m.difficulty
    diff_label = DIFFICULTY_LABEL.get(diff, diff)

    return (
        "🧩 <b>Миссия</b>\n\n"
        f"ID: <code>{m.id}</code>\n"
        f"Статус: {'✅ active' if m.active else '🚫 inactive'}\n"
        f"Архив: {'🗄 да' if is_archived else '—'}\n"
        f"Difficulty: <b>{diff_label}</b>\n"
        f"Points: <b>{points}</b>\n"
        f"Теги: {tags_txt}\n"
        f"Group ID: {group_id if group_id else '—'}\n"
        f"Sequence order: {seq if seq is not None else '—'}\n\n"
        f"Текст:\n{m.text}"
    )


@router.callback_query(F.data == "admin_manage_missions")
async def cb_admin_manage_missions(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    # ВАЖНО: difficulty в системе уже используется как basic/elite (lowercase),
    # поэтому в CRUD тоже фиксируем этот формат.
    total = (await db_session.execute(select(func.count(Mission.id)))).scalar_one() or 0
    active = (await db_session.execute(select(func.count(Mission.id)).where(Mission.active.is_(True)))).scalar_one() or 0
    archived_col = _mission_is_archived_col()
    archived = (await db_session.execute(select(func.count(Mission.id)).where(archived_col.is_(True)))).scalar_one() or 0

    text = (
        "⚙️ <b>Управление миссиями</b>\n\n"
        f"Всего: <b>{int(total)}</b>\n"
        f"Активных: <b>{int(active)}</b>\n"
        f"В архиве: <b>{int(archived)}</b>\n\n"
        "Дальше — через кнопки ниже."
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_missions_manage_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("am_list:"))
async def cb_am_list(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    _, page_s, flt = callback.data.split(":", 2)
    page = max(int(page_s), 0)
    page_size = 5
    offset = page * page_size

    archived_col = _mission_is_archived_col()

    conditions = []
    if flt == "active":
        conditions.append(Mission.active.is_(True))
        conditions.append(archived_col.is_(False))
    elif flt == "archived":
        conditions.append(archived_col.is_(True))

    base = select(Mission)
    if conditions:
        base = base.where(and_(*conditions))

    total = (await db_session.execute(select(func.count(Mission.id)).select_from(base.subquery()))).scalar_one() or 0
    total_pages = max(1, (int(total) + page_size - 1) // page_size)
    if page > total_pages - 1:
        page = total_pages - 1
        offset = page * page_size

    rows = (
        await db_session.execute(
            base.order_by(desc(Mission.id)).limit(page_size).offset(offset)
        )
    ).scalars().all()

    if not rows:
        text = "📃 <b>Миссии</b>\n\nПусто."
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_missions_list_keyboard(page, flt, total_pages))
        await callback.answer()
        return

    lines = [f"📃 <b>Миссии</b> (стр. {page+1}/{total_pages})\n"]
    kb_rows = []

    for m in rows:
        points = getattr(m, "points_reward", getattr(m, "pointsreward", 10))
        is_archived = bool(getattr(m, "is_archived", getattr(m, "isarchived", False)))
        status = "✅" if m.active else "🚫"
        arch = "🗄" if is_archived else ""
        diff_label = DIFFICULTY_LABEL.get(m.difficulty, m.difficulty)

        lines.append(f"{status}{arch} <code>{m.id}</code> — {diff_label} / {points} pts")
        lines.append((m.text[:70] + "…") if len(m.text) > 70 else m.text)
        lines.append("")

        kb_rows.append([InlineKeyboardButton(text=f"👁 {m.id}", callback_data=f"am_view:{m.id}")])

    kb = _missions_list_keyboard(page, flt, total_pages)
    kb.inline_keyboard = kb_rows + kb.inline_keyboard

    await callback.message.edit_text("\n".join(lines).strip(), parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("am_view:"))
async def cb_am_view(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    mission_id = int(callback.data.split(":")[1])
    m = (await db_session.execute(select(Mission).where(Mission.id == mission_id))).scalar_one_or_none()
    if not m:
        await callback.answer("Миссия не найдена", show_alert=True)
        return

    is_archived = bool(getattr(m, "is_archived", getattr(m, "isarchived", False)))
    await callback.message.edit_text(
        _mission_card_text(m),
        parse_mode="HTML",
        reply_markup=_mission_card_keyboard(m.id, m.active, is_archived),
    )
    await callback.answer()


@router.callback_query(F.data == "am_create")
async def cb_am_create(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminStates.mission_create_text)
    await callback.message.answer("Введите текст миссии (или cancel):", parse_mode="HTML")
    await callback.answer()


@router.message(AdminStates.mission_create_text)
async def msg_am_create_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    if message.text and message.text.strip().lower() in ("cancel", "/cancel", "отмена"):
        await state.clear()
        await message.answer("Отменено.", parse_mode="HTML")
        return

    text = (message.text or "").strip()
    if len(text) < 5:
        await message.answer("Слишком коротко. Введите нормальный текст.", parse_mode="HTML")
        return

    await state.update_data(text=text)
    await state.set_state(AdminStates.mission_create_tags)
    await message.answer("Теги через запятую (или '-' если без тегов):", parse_mode="HTML")


@router.message(AdminStates.mission_create_tags)
async def msg_am_create_tags(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    if message.text and message.text.strip().lower() in ("cancel", "/cancel", "отмена"):
        await state.clear()
        await message.answer("Отменено.", parse_mode="HTML")
        return

    tags = parse_tags(message.text or "")
    await state.update_data(tags=tags)
    await state.set_state(AdminStates.mission_create_difficulty)
    await message.answer("Difficulty: basic или elite:", parse_mode="HTML")


@router.message(AdminStates.mission_create_difficulty)
async def msg_am_create_difficulty(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    if message.text and message.text.strip().lower() in ("cancel", "/cancel", "отмена"):
        await state.clear()
        await message.answer("Отменено.", parse_mode="HTML")
        return

    try:
        difficulty = normalize_difficulty(message.text or "")
    except ValueError:
        await message.answer("Неверно. Введите строго: basic или elite.", parse_mode="HTML")
        return

    await state.update_data(difficulty=difficulty)
    await state.set_state(AdminStates.mission_create_points)
    await message.answer(f"Очки (Enter = {DEFAULT_POINTS[difficulty]}, диапазон 1-100):", parse_mode="HTML")


@router.message(AdminStates.mission_create_points)
async def msg_am_create_points(message: Message, state: FSMContext, db_session):
    if not is_admin(message.from_user.id):
        return

    if message.text and message.text.strip().lower() in ("cancel", "/cancel", "отмена"):
        await state.clear()
        await message.answer("Отменено.", parse_mode="HTML")
        return

    data = await state.get_data()
    difficulty = data["difficulty"]

    raw = (message.text or "").strip()
    if raw == "":
        points = DEFAULT_POINTS[difficulty]
    else:
        try:
            points = int(raw)
        except ValueError:
            await message.answer("Введите число 1-100 или пусто (Enter).", parse_mode="HTML")
            return
        if points < 1 or points > 100:
            await message.answer("Диапазон 1-100.", parse_mode="HTML")
            return

    m = Mission(
        text=data["text"],
        difficulty=difficulty,
        active=True,
    )
    # points
    if hasattr(m, "points_reward"):
        m.points_reward = points
    else:
        m.pointsreward = points

    # archive flags
    if hasattr(m, "is_archived"):
        m.is_archived = False
    else:
        m.isarchived = False

    # group flags
    if hasattr(m, "is_group_mission"):
        m.is_group_mission = False
    else:
        m.isgroupmission = False

    set_tags(m, data.get("tags", []))

    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)

    await state.clear()
    await message.answer(f"✅ Создано. ID: <code>{m.id}</code>", parse_mode="HTML")
    # показать карточку
    is_archived = bool(getattr(m, "is_archived", getattr(m, "isarchived", False)))
    await message.answer(_mission_card_text(m), parse_mode="HTML", reply_markup=_mission_card_keyboard(m.id, m.active, is_archived))


@router.callback_query(F.data == "am_find")
async def cb_am_find(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    await state.clear()
    await state.set_state(AdminStates.mission_find_id)
    await callback.message.answer("Введите ID миссии (или cancel):", parse_mode="HTML")
    await callback.answer()


@router.message(AdminStates.mission_find_id)
async def msg_am_find(message: Message, state: FSMContext, db_session):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.strip().lower() in ("cancel", "/cancel", "отмена"):
        await state.clear()
        await message.answer("Отменено.", parse_mode="HTML")
        return
    try:
        mid = int((message.text or "").strip())
    except ValueError:
        await message.answer("Нужно число (ID).", parse_mode="HTML")
        return

    m = (await db_session.execute(select(Mission).where(Mission.id == mid))).scalar_one_or_none()
    if not m:
        await message.answer("Миссия не найдена.", parse_mode="HTML")
        return

    await state.clear()
    is_archived = bool(getattr(m, "is_archived", getattr(m, "isarchived", False)))
    await message.answer(_mission_card_text(m), parse_mode="HTML", reply_markup=_mission_card_keyboard(m.id, m.active, is_archived))


@router.callback_query(F.data.startswith("am_toggle:"))
async def cb_am_toggle(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    mid = int(callback.data.split(":")[1])
    m = (await db_session.execute(select(Mission).where(Mission.id == mid))).scalar_one_or_none()
    if not m:
        await callback.answer("Миссия не найдена", show_alert=True)
        return
    m.active = not m.active
    await db_session.commit()
    await callback.answer("Ок")
    callback.data = f"am_view:{mid}"
    await cb_am_view(callback, db_session)


@router.callback_query(F.data.startswith("am_archive:"))
async def cb_am_archive(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    mid = int(callback.data.split(":")[1])
    m = (await db_session.execute(select(Mission).where(Mission.id == mid))).scalar_one_or_none()
    if not m:
        await callback.answer("Миссия не найдена", show_alert=True)
        return

    # toggle archived
    is_archived_now = bool(getattr(m, "is_archived", getattr(m, "isarchived", False)))
    new_val = not is_archived_now

    if hasattr(m, "is_archived"):
        m.is_archived = new_val
    else:
        m.isarchived = new_val

    # профессиональная практика: если архивируем — выключаем
    if new_val:
        m.active = False

    await db_session.commit()
    await callback.answer("Ок")
    callback.data = f"am_view:{mid}"
    await cb_am_view(callback, db_session)


@router.callback_query(F.data.startswith("am_delete_confirm:"))
async def cb_am_delete_confirm(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    mid = int(callback.data.split(":")[1])
    m = (await db_session.execute(select(Mission).where(Mission.id == mid))).scalar_one_or_none()
    if not m:
        await callback.answer("Миссия не найдена", show_alert=True)
        return

    await callback.message.edit_text(
        f"🗑 Точно удалить миссию <code>{mid}</code>? Это hard-delete.",
        parse_mode="HTML",
        reply_markup=_mission_delete_confirm_keyboard(mid),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("am_delete:"))
async def cb_am_delete(callback: CallbackQuery, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    mid = int(callback.data.split(":")[1])
    m = (await db_session.execute(select(Mission).where(Mission.id == mid))).scalar_one_or_none()
    if not m:
        await callback.answer("Миссия не найдена", show_alert=True)
        return

    await db_session.delete(m)
    await db_session.commit()

    await callback.answer("Удалено", show_alert=True)
    # возвращаемся к списку
    callback.data = "am_list:0:all"
    await cb_am_list(callback, db_session)


@router.callback_query(F.data.startswith("am_edit:"))
async def cb_am_edit_start(callback: CallbackQuery, state: FSMContext, db_session):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    # am_edit:<field>:<mission_id>
    _, field, mid_s = callback.data.split(":", 2)
    mid = int(mid_s)

    m = (await db_session.execute(select(Mission).where(Mission.id == mid))).scalar_one_or_none()
    if not m:
        await callback.answer("Миссия не найдена", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminStates.mission_edit_value)
    await state.update_data(edit_field=field, edit_mission_id=mid)

    prompts = {
        "text": "✏️ Введите новый текст миссии (или <code>skip</code> / <code>cancel</code>):",
        "tags": "🏷 Введите теги через запятую (или <code>-</code> чтобы очистить, или <code>cancel</code>):",
        "difficulty": "🎚 Введите difficulty: <code>basic</code> или <code>elite</code> (или <code>cancel</code>):",
        "points": "🎯 Введите points (1-100) (или <code>cancel</code>):",
        "group": "📦 Введите ID группы, или <code>0</code> чтобы убрать из группы (или <code>cancel</code>):",
        "order": "↕️ Введите sequence order (число), или <code>-</code> чтобы очистить (или <code>cancel</code>):",
    }

    await callback.message.answer(prompts.get(field, "Введите значение (или cancel):"), parse_mode="HTML")
    await callback.answer()


@router.message(AdminStates.mission_edit_value)
async def msg_am_edit_value(message: Message, state: FSMContext, db_session):
    if not is_admin(message.from_user.id):
        return

    if message.text and message.text.strip().lower() in ("cancel", "/cancel", "отмена"):
        await state.clear()
        await message.answer("Отменено.", parse_mode="HTML")
        return

    data = await state.get_data()
    field = data.get("edit_field")
    mid = int(data.get("edit_mission_id") or 0)

    m = (await db_session.execute(select(Mission).where(Mission.id == mid))).scalar_one_or_none()
    if not m:
        await state.clear()
        await message.answer("Миссия не найдена.", parse_mode="HTML")
        return

    raw = message.text or ""

    # helpers for setattr compatibility
    def set_points(val: int) -> None:
        if hasattr(m, "points_reward"):
            m.points_reward = val
        else:
            m.pointsreward = val

    def set_archived(val: bool) -> None:
        if hasattr(m, "is_archived"):
            m.is_archived = val
        else:
            m.isarchived = val

    def set_group_id(val: Optional[int]) -> None:
        if hasattr(m, "group_id"):
            m.group_id = val
        else:
            m.groupid = val

    def set_is_group(val: bool) -> None:
        if hasattr(m, "is_group_mission"):
            m.is_group_mission = val
        else:
            m.isgroupmission = val

    def set_sequence_order(val: Optional[int]) -> None:
        if hasattr(m, "sequence_order"):
            m.sequence_order = val
        else:
            m.sequenceorder = val

    try:
        if field == "text":
            v = raw.strip()
            if v.lower() != "skip":
                if len(v) < 5:
                    await message.answer("Слишком коротко.", parse_mode="HTML")
                    return
                m.text = v

        elif field == "tags":
            tags = parse_tags(raw)
            set_tags(m, tags)

        elif field == "difficulty":
            m.difficulty = normalize_difficulty(raw)

        elif field == "points":
            pts = int(raw.strip())
            if pts < 1 or pts > 100:
                await message.answer("Диапазон 1-100.", parse_mode="HTML")
                return
            set_points(pts)

        elif field == "group":
            gid = int(raw.strip())
            if gid == 0:
                set_group_id(None)
                set_is_group(False)
                set_sequence_order(None)
            else:
                if MissionGroup is None:
                    await message.answer("Модель MissionGroup не подключена в проекте.", parse_mode="HTML")
                    return

                g = (await db_session.execute(select(MissionGroup).where(MissionGroup.id == gid))).scalar_one_or_none()
                if not g:
                    await message.answer("Группа не найдена.", parse_mode="HTML")
                    return

                set_group_id(gid)
                set_is_group(True)

        elif field == "order":
            s = raw.strip()
            if s in {"-", "—"}:
                set_sequence_order(None)
            else:
                order = int(s)
                if order < 1 or order > 1000:
                    await message.answer("Порядок: 1-1000.", parse_mode="HTML")
                    return
                set_sequence_order(order)

        else:
            await message.answer("Неизвестное поле.", parse_mode="HTML")
            return

        # если миссия в архиве — держим inactive
        if bool(getattr(m, "is_archived", getattr(m, "isarchived", False))):
            m.active = False

        await db_session.commit()
        await db_session.refresh(m)

    except ValueError:
        await message.answer("Неверный формат значения.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"am_edit_value error: {e}", exc_info=True)
        await message.answer("❌ Ошибка при сохранении.", parse_mode="HTML")
        return

    await state.clear()
    await message.answer("✅ Обновлено.", parse_mode="HTML")

    is_archived = bool(getattr(m, "is_archived", getattr(m, "isarchived", False)))
    await message.answer(
        _mission_card_text(m),
        parse_mode="HTML",
        reply_markup=_mission_card_keyboard(m.id, m.active, is_archived),
    )