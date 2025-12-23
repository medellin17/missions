#/handlers/admin/users.py

"""
Admin handler для управления пользователями: 
- Просмотр списка пользователей
- Блокировка/разблокировка
- Просмотр профиля пользователя
"""

from __future__ import annotations

import logging
from typing import List

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from utils.admin import is_admin

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("admin_users"))
async def cmd_admin_users(message: Message, db_session: AsyncSession) -> None:
    """
    Команда /admin_users — список всех пользователей (только для админов).
    """
    if not is_admin(message.from_user. id):
        await message.answer("❌ У вас нет прав администратора.")
        return

    try:
        # Получаем пользователей
        result = await db_session.execute(
            select(User).order_by(desc(User.created_at)).limit(20)
        )
        users = result.scalars().all()

        if not users:
            await message.answer("📭 Пользователей не найдено.")
            return

        # Формируем текст
        text = f"👥 <b>Список пользователей</b> ({len(users)})\n\n"

        for user in users[: 10]: 
            status = "🚫" if getattr(user, "is_banned", False) else "✅"
            username = getattr(user, "username", f"ID {user.user_id}") or f"ID {user.user_id}"

            text += (
                f"{status} <b>{username}</b>\n"
                f"   ID: <code>{user.user_id}</code>\n"
                f"   Уровень: {user.level} | Очки: {user.points}\n"
                f"   Присоединился: {user.created_at. strftime('%d.%m. %Y')}\n\n"
            )

        # Кнопки
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_users_refresh")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")],
            ]
        )

        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error in cmd_admin_users: {e}", exc_info=True)
        await message. answer("❌ Ошибка при получении списка пользователей.")


@router.callback_query(F. data == "admin_users_refresh")
async def callback_refresh_users(callback:  CallbackQuery, db_session:  AsyncSession) -> None:
    """Обновить список пользователей"""
    await cmd_admin_users(
        Message(
            message_id=callback.message.message_id,
            chat=callback.message.chat,
            from_user=callback.from_user,
            text="/admin_users",
        ),
        db_session,
    )
    await callback.answer("🔄 Обновлено")


@router.callback_query(F.data. startswith("admin_user: "))
async def callback_view_user(callback: CallbackQuery, db_session: AsyncSession) -> None:
    """
    Просмотр профиля конкретного пользователя. 
    """
    if not is_admin(callback.from_user.id):
        await callback. answer("❌ Доступ запрещён", show_alert=True)
        return

    try:
        user_id = int(callback.data.split(":")[1])

        result = await db_session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        is_banned = getattr(user, "is_banned", False)
        ban_status = "🚫 ЗАБЛОКИРОВАН" if is_banned else "✅ Активен"

        text = (
            f"👤 <b>Профиль пользователя</b>\n\n"
            f"ID: <code>{user.user_id}</code>\n"
            f"Статус: {ban_status}\n"
            f"⭐ Уровень: {user.level}\n"
            f"🎯 Очки: {user. points}\n"
            f"⚡ Заряды: {user.charges}/3\n"
            f"📅 Создан: {user.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        )

        # Кнопки действий
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚫 Заблокировать" if not is_banned else "✅ Разблокировать",
                        callback_data=f"admin_toggle_ban:{user_id}"
                    )
                ],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_users_refresh")],
            ]
        )

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()

    except Exception as e: 
        logger.error(f"Error in callback_view_user: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F. data.startswith("admin_toggle_ban:"))
async def callback_toggle_ban(callback: CallbackQuery, db_session: AsyncSession) -> None:
    """
    Заблокировать/разблокировать пользователя. 
    """
    if not is_admin(callback.from_user. id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return

    try:
        user_id = int(callback.data.split(": ")[1])

        result = await db_session. execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback. answer("❌ Пользователь не найден", show_alert=True)
            return

        # Переключаем статус
        is_banned = getattr(user, "is_banned", False)
        user.is_banned = not is_banned
        await db_session.commit()

        action = "заблокирован" if not is_banned else "разблокирован"
        await callback.answer(f"✅ Пользователь {action}")

        # Обновляем текст
        await callback_view_user(callback, db_session)

    except Exception as e:
        logger.error(f"Error in callback_toggle_ban: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)