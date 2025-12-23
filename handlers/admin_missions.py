# handlers/admin_missions.py

import logging
from dataclasses import dataclass

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from sqlalchemy import select, func, desc

from core.config import settings
from models.mission import Mission
from models.mission_group import MissionGroup

from keyboards.admin_missions_kb import (
    missions_manage_keyboard,
    missions_list_keyboard,
    mission_card_keyboard,
    delete_confirm_keyboard,
)
from utils.mission_validation import (
    normalize_difficulty,
    parse_tags,
    DEFAULT_POINTS,
    DIFFICULTY_LABELS,
)

router = Router()
logger = logging.getLogger(__name__)

PAGE_SIZE = 5


def is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


class AdminMissionStates(StatesGroup):
    creating_text = State()
    creating_tags = State()
    creating_difficulty = State()
    creating_points = State()

    editing_field = State()  # универсальное состояние ввода значения поля


@dataclass
class EditCtx:
    field: str
    mission_id: int


def _get_tags(mission: Mission) -> list[str]:
    # поддержка разных реализаций (tags property vs tagslist string)
    if hasattr(mission, "tags") and mission.tags:
        return list(mission.tags)
    raw = getattr(mission, "tagslist", None) or ""
    return parse_tags(raw)


def _set_tags(mission: Mission, tags: list[str]) -> None:
    # сохраняем и в tagslist, и в tags (если есть), чтобы не зависеть от реализации модели
    if hasattr(mission, "tagslist"):
        mission.tagslist = ", ".join(tags) if tags else ""
    if hasattr(mission, "tags"):
        mission.tags = tags


def _difficulty_label(value: str) -> str:
    return DIFFICULTY_LABELS.get(value, value)


def _mission_card_text(m: Mission) -> str:
    tags = _get_tags(m)
    tags_text = ", ".join(tags) if tags else "—"
    group_id = getattr(m, "groupid", None)
    seq = getattr(m, "sequenceorder", None)

    return (
        f"🧩 <b>Миссия</b>\n"
        f"ID: <code>{m.id}</code>\n"
        f"Статус: {'✅ active' if m.active else '🚫 inactive'}\n"
        f"Архив: {'🗄 да' if getattr(m, 'isarchived', False) else '—'}\n\n"
        f"Difficulty: <b>{_difficulty_label(m.difficulty)}</b>\n"
        f"Points: <b>{m.pointsreward}</b>\n"
        f"Теги: {tags_text}\n"
        f"Group ID: {group_id if group_id else '—'}\n"
        f"Sequence order: {seq if seq is not None else '—'}\n\n"
        f"Текст:\n{m.text}"
    )


async def _get_mission(dbsession, mission_id: int) -> Mission | None:
    res = await dbsession.execute(select(Mission).where(Mission.id == mission_id))
    return res.scalar_one_or_none()


@router.callback_query(F.data == "am:menu")
async def am_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text(
        "⚙️ <b>Управление миссиями</b>",
        parse_mode="HTML",
        reply_markup=missions_manage_keyboard(),
    )
    await callback.answer()

@router.callback_query(F.data == "admin_manage_missions")
async def cb_admin_manage_missions(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    # просто открываем меню миссий (тот же экран, что am:menu)
    await callback.message.edit_text(
        "⚙️ <b>Управление миссиями</b>",
        parse_mode="HTML",
        reply_markup=missions_manage_keyboard(),
    )
    await callback.answer()

@router.callback_query(F.data.startswith("am:list:"))
async def am_list(callback: CallbackQuery, dbsession):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    _, _, page_str, flt = callback.data.split(":", 3)
    page = max(int(page_str), 0)

    conditions = []
    if flt == "active":
        conditions.append(Mission.active.is_(True))
        conditions.append(Mission.isarchived.is_(False))
    elif flt == "archived":
        conditions.append(Mission.isarchived.is_(True))
    else:
        # all
        pass

    base_q = select(Mission)
    if conditions:
        from sqlalchemy import and_
        base_q = base_q.where(and_(*conditions))

    total_res = await dbsession.execute(select(func.count(Mission.id)).select_from(base_q.subquery()))
    total = int(total_res.scalar() or 0)

    offset = page * PAGE_SIZE
    res = await dbsession.execute(
        base_q.order_by(desc(Mission.id)).limit(PAGE_SIZE).offset(offset)
    )
    missions = res.scalars().all()

    if total == 0:
        text = "📃 <b>Миссии</b>\n\nПока пусто."
    else:
        lines = [f"📃 <b>Миссии</b> (показ {offset+1}-{min(offset+PAGE_SIZE, total)} из {total})\n"]
        for m in missions:
            status = "✅" if m.active else "🚫"
            arch = "🗄" if m.isarchived else ""
            lines.append(
                f"{status}{arch} <code>{m.id}</code> "
                f"{_difficulty_label(m.difficulty)} / {m.pointsreward} pts\n"
                f"{(m.text[:60] + '…') if len(m.text) > 60 else m.text}\n"
                f"👉 /view: {m.id} (кнопкой ниже)"
            )
            lines.append("")  # пустая строка
        # кнопки "view" отдельным рядом
        lines.append("Нажми на ID ниже для карточки:")
        text = "\n".join(lines)

    has_prev = page > 0
    has_next = (offset + PAGE_SIZE) < total

    # Список ID кнопками
    id_rows = []
    for m in missions:
        id_rows.append([InlineKeyboardButton(text=f"👁 {m.id}", callback_data=f"am:view:{m.id}")])

    kb = missions_list_keyboard(page, flt, has_prev, has_next)
    # приклеим кнопки ID сверху
    kb.inline_keyboard = id_rows + kb.inline_keyboard

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("am:view:"))
async def am_view(callback: CallbackQuery, dbsession):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    mission_id = int(callback.data.split(":")[2])
    m = await _get_mission(dbsession, mission_id)
    if not m:
        await callback.answer("Миссия не найдена", show_alert=True)
        return

    await callback.message.edit_text(
        _mission_card_text(m),
        parse_mode="HTML",
        reply_markup=mission_card_keyboard(m.id, m.isarchived, m.active),
    )
    await callback.answer()


@router.callback_query(F.data == "am:create")
async def am_create_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminMissionStates.creating_text)
    await callback.message.answer("Введите текст миссии (или 'cancel'):", parse_mode="HTML")
    await callback.answer()


@router.message(AdminMissionStates.creating_text)
async def am_create_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.lower() == "cancel":
        await state.clear()
        await message.answer("Отменено.")
        return

    text = (message.text or "").strip()
    if len(text) < 5:
        await message.answer("Слишком коротко. Введите нормальный текст миссии.")
        return

    await state.update_data(text=text)
    await state.set_state(AdminMissionStates.creating_tags)
    await message.answer("Теги через запятую (или '-' если без тегов):")


@router.message(AdminMissionStates.creating_tags)
async def am_create_tags(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.lower() == "cancel":
        await state.clear()
        await message.answer("Отменено.")
        return

    tags = parse_tags(message.text or "")
    await state.update_data(tags=tags)
    await state.set_state(AdminMissionStates.creating_difficulty)
    await message.answer("Difficulty: basic или elite:")


@router.message(AdminMissionStates.creating_difficulty)
async def am_create_difficulty(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.lower() == "cancel":
        await state.clear()
        await message.answer("Отменено.")
        return

    try:
        difficulty = normalize_difficulty(message.text)
    except ValueError:
        await message.answer("Неверно. Введите строго: basic или elite.")
        return

    await state.update_data(difficulty=difficulty)
    await state.set_state(AdminMissionStates.creating_points)
    await message.answer(f"Сколько очков? (Enter = {DEFAULT_POINTS[difficulty]}, диапазон 1-100)")


@router.message(AdminMissionStates.creating_points)
async def am_create_points(message: Message, state: FSMContext, dbsession):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.lower() == "cancel":
        await state.clear()
        await message.answer("Отменено.")
        return

    data = await state.get_data()
    difficulty = data["difficulty"]
