#/handlers/mission_groups_user.py

"""
Handler'ы для пользователей (не админов):
- Просмотр доступных групп
- Присоединение к группе
- Просмот прогресса
- Завершение группы
"""

from __future__ import annotations

import logging
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.mission_group import MissionGroup, GroupType, AccessType
from models.user import User
from models.user_group_progress import UserGroupProgress
from services.user_service import UserService
from services.user_progress_service import UserProgressService
from core.exceptions import UnauthorizedAccess

router = Router()
logger = logging.getLogger(__name__)


class GroupStates(StatesGroup):
    """FSM состояния для работы с группами"""
    confirming_join = State()


@router.message(Command("groups"))
@router.callback_query(F.data == "show_groups")
async def cmd_show_groups(event, db_session: AsyncSession) -> None:
    """
    Показать список доступных групп миссий
    Может быть вызвано как /groups или callback
    """
    try: 
        # Определяем тип события (message или callback)
        user_id = event.from_user.id
        message = event if isinstance(event, Message) else event.message
        
        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(user_id)
        
        # Получаем все активные и опубликованные группы
        result = await db_session.execute(
            select(MissionGroup).where(
                and_(
                    MissionGroup. is_active == True,
                    MissionGroup.is_published == True
                )
            ).order_by(MissionGroup.name)
        )
        groups = result.scalars().all()
        
        if not groups:
            text = "📦 <b>Группы миссий</b>\n\nПока групп не найдено."
            await message.answer(text, parse_mode="HTML")
            return
        
        # Получаем прогресс пользователя во всех группах
        progress_result = await db_session.execute(
            select(UserGroupProgress).where(
                UserGroupProgress.user_id == user_id
            )
        )
        user_progress_dict = {p.group_id: p for p in progress_result.scalars().all()}
        
        # Форматируем список групп
        text = "📦 <b>Доступные группы миссий</b>\n\n"
        buttons = []
        
        for i, group in enumerate(groups, 1):
            # Проверяем доступ
            can_access = await _check_group_access(group, user)
            
            # Проверяем прогресс
            progress = user_progress_dict.get(group.id)
            status = "✅ Завершена" if progress and progress.is_completed else "🔄 В прогрессе" if progress else "🔓 Доступна"
            
            if not can_access:
                status = f"🔒 Требуется уровень {group.required_level}"
            
            # Формируем информацию о группе
            emoji = group.emoji or "🎯"
            text += (
                f"{i}.  {emoji} <b>{group. name}</b>\n"
                f"   {group.description or 'Нет описания'}\n"
                f"   Статус: {status}\n"
                f"   Миссий: {group.total_missions}\n"
                f"   Тип: {'🎲 Случайные' if group.group_type == GroupType.RANDOM else '➡️ По порядку'}\n\n"
            )
            
            # Добавляем кнопку
            if can_access:
                if not progress:
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"🚀 Начать {emoji}",
                            callback_data=f"group_join:{group.id}"
                        )
                    ])
                elif not progress.is_completed:
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"▶️ Продолжить {emoji}",
                            callback_data=f"group_progress:{group.id}"
                        )
                    ])
                else:
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"🔄 Повторить {emoji}",
                            callback_data=f"group_restart:{group.id}"
                        )
                    ])
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons if buttons else [[
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
        ]])
        
        if isinstance(event, Message):
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
            await event.answer()
            
    except Exception as e:
        logger.error(f"Error in cmd_show_groups: {e}", exc_info=True)
        text = "❌ Ошибка при получении групп"
        if isinstance(event, Message):
            await event.answer(text)
        else:
            await event.answer(text, show_alert=True)


@router.callback_query(F.data. startswith("group_join:"))
async def callback_group_join(callback: CallbackQuery, db_session: AsyncSession, state: FSMContext) -> None:
    """
    Присоединиться к группе миссий
    """
    try:
        group_id = int(callback.data.split(": ")[1])
        user_id = callback.from_user.id
        
        # Получаем группу
        group_result = await db_session.execute(
            select(MissionGroup).where(MissionGroup.id == group_id)
        )
        group = group_result.scalar_one_or_none()
        
        if not group:
            await callback.answer("❌ Группа не найдена", show_alert=True)
            return
        
        # Проверяем доступ
        user_service = UserService(db_session)
        user = await user_service.get_or_create_user(user_id)
        
        can_access = await _check_group_access(group, user)
        if not can_access:
            raise UnauthorizedAccess(user_id, f"join_group_{group_id}")
        
        # Проверяем нет ли уже прогресса
        progress_result = await db_session.execute(
            select(UserGroupProgress).where(
                and_(
                    UserGroupProgress. user_id == user_id,
                    UserGroupProgress.group_id == group_id,
                    UserGroupProgress.is_completed == False
                )
            )
        )
        existing = progress_result.scalar_one_or_none()
        
        if existing:
            await callback.answer("⚠️ Вы уже начали эту группу.  Используйте /mission для продолжения.")
            return
        
        # Подтверждение
        confirm_text = (
            f"🎯 <b>Начать группу? </b>\n\n"
            f"<b>{group.emoji} {group.name}</b>\n"
            f"{group.description or 'Нет описания'}\n\n"
            f"📊 Миссий: {group.total_missions}\n"
            f"⭐ Тип: {'🎲 Случайные' if group.group_type == GroupType.RANDOM else '➡️ По порядку'}\n\n"
            f"После старта вы будете получать миссии из этой группы!"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Начать", callback_data=f"group_confirm_join:{group_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="show_groups")
            ]
        ])
        
        await callback. message.edit_text(confirm_text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()
        
    except UnauthorizedAccess as e: 
        await callback.answer(
            f"❌ У вас нет доступа к этой группе.  {e}",
            show_alert=True
        )
    except Exception as e:
        logger.error(f"Error in callback_group_join: {e}", exc_info=True)
        await callback. answer("❌ Ошибка", show_alert=True)


@router.callback_query(F. data.startswith("group_confirm_join:"))
async def callback_group_confirm_join(callback: CallbackQuery, db_session: AsyncSession) -> None:
    """
    Подтверждение присоединения к группе
    """
    try:
        group_id = int(callback.data. split(":")[1])
        user_id = callback.from_user.id
        
        progress_service = UserProgressService(db_session)
        
        # Создаем прогресс
        progress = await progress_service.get_or_create_progress(user_id, group_id)
        
        # Получаем группу для информации
        group_result = await db_session.execute(
            select(MissionGroup).where(MissionGroup.id == group_id)
        )
        group = group_result.scalar_one_or_none()
        
        text = (
            f"✅ <b>Вы начали группу! </b>\n\n"
            f"{group.emoji} <b>{group.name}</b>\n\n"
            f"Первая миссия ждет вас!  Используйте <code>/mission</code> чтобы начать.\n\n"
            f"📊 Ваш прогресс:  0/{group.total_missions}"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать миссию", callback_data="get_mission")],
            [InlineKeyboardButton(text="📦 Мои группы", callback_data="show_groups")]
        ])
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer("✅ Группа начата!")
        
    except Exception as e:
        logger.error(f"Error in callback_group_confirm_join: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при присоединении", show_alert=True)


@router.callback_query(F.data.startswith("group_progress:"))
async def callback_group_progress(callback: CallbackQuery, db_session: AsyncSession) -> None:
    """
    Показать прогресс в группе
    """
    try:
        group_id = int(callback.data.split(": ")[1])
        user_id = callback.from_user.id
        
        # Получаем группу
        group_result = await db_session.execute(
            select(MissionGroup).where(MissionGroup.id == group_id)
        )
        group = group_result.scalar_one_or_none()
        
        # Получаем прогресс
        progress_result = await db_session.execute(
            select(UserGroupProgress).where(
                and_(
                    UserGroupProgress. user_id == user_id,
                    UserGroupProgress.group_id == group_id
                )
            )
        )
        progress = progress_result.scalar_one_or_none()
        
        if not progress:
            await callback.answer("❌ Вы не начали эту группу", show_alert=True)
            return
        
        # Вычисляем прогресс
        completed = progress.completed_missions or 0
        total = progress. total_missions or group.total_missions or 1
        percent = int((completed / total * 100)) if total > 0 else 0
        
        progress_bar = _make_progress_bar(percent, 10)
        
        text = (
            f"{group.emoji} <b>{group. name}</b>\n\n"
            f"<b>Ваш прогресс:</b>\n"
            f"{progress_bar} {percent}%\n\n"
            f"✅ Выполнено: {completed}/{total} миссий\n"
            f"⭐ Очков получено: {progress.points_earned or 0}\n"
            f"🏆 Бонус получен: {'Да' if progress.bonus_earned else 'Нет'}\n\n"
            f"Продолжите выполнять миссии командой /mission"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Следующая миссия", callback_data="get_mission")],
            [InlineKeyboardButton(text="📦 Все группы", callback_data="show_groups")]
        ])
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error in callback_group_progress: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F. data.startswith("group_restart:"))
async def callback_group_restart(callback: CallbackQuery, db_session: AsyncSession) -> None:
    """
    Перезапустить завершенную группу
    """
    try:
        group_id = int(callback.data. split(":")[1])
        user_id = callback.from_user.id
        
        progress_service = UserProgressService(db_session)
        
        # Удаляем старый прогресс
        old_progress_result = await db_session.execute(
            select(UserGroupProgress).where(
                and_(
                    UserGroupProgress.user_id == user_id,
                    UserGroupProgress.group_id == group_id
                )
            )
        )
        old_progress = old_progress_result.scalar_one_or_none()
        
        if old_progress:
            await db_session.delete(old_progress)
        
        # Создаем новый прогресс
        new_progress = await progress_service. get_or_create_progress(user_id, group_id)
        
        await callback.answer("✅ Группа перезагружена!  Используйте /mission")
        
    except Exception as e:
        logger.error(f"Error in callback_group_restart: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


# =========================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================================

async def _check_group_access(group: MissionGroup, user:  User) -> bool:
    """
    Проверить доступ пользователя к группе
    
    Returns:
        True если у пользователя есть доступ, False иначе
    """
    if group.access_type == AccessType.PUBLIC:
        return True
    
    if group.access_type == AccessType.LEVEL_BASED:
        return user.level >= group.required_level
    
    if group. access_type == AccessType. PRIVATE:
        # Для PRIVATE проверяем специальный доступ в UserGroupAccess
        # Пока просто вернем False
        return False
    
    return False


def _make_progress_bar(percent: int, length: int = 10) -> str:
    """
    Создать ASCII прогресс-бар
    
    Args:
        percent:  Процент заполнения (0-100)
        length: Длина бара
        
    Returns:
        Строка вида: ████████░░ (80%)
    """
    filled = int(length * percent / 100)
    bar = "█" * filled + "░" * (length - filled)
    return bar