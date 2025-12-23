# handlers/admin_archive.py

"""Админ-панель для управления архивом миссий"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from models.mission import Mission
from utils.admin import is_admin

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "admin_view_archive")
async def view_archive(callback: CallbackQuery, db_session: AsyncSession):
    """Просмотр архивных миссий"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    try:
        # Получаем архивные миссии
        result = await db_session.execute(
            select(Mission)
            .where(Mission.is_archived == True)
            .order_by(Mission.archived_at.desc())
            .limit(20)
        )
        archived_missions = result.scalars().all()
        
        if not archived_missions:
            await callback.message.edit_text(
                "📦 <b>Архив миссий</b>\n\n"
                "Архив пуст.",
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        # Формируем список
        text = "📦 <b>Архивные миссии</b>\n\n"
        
        for mission in archived_missions[:10]:
            text += (
                f"🔹 ID: {mission.id}\n"
                f"   {mission.text[:60]}...\n"
                f"   Версия: v{mission.version}\n"
                f"   Архивирована: {mission.archived_at.strftime('%d.%m.%Y')}\n\n"
            )
        
        if len(archived_missions) > 10:
            text += f"... и ещё {len(archived_missions) - 10} миссий\n"
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error viewing archive: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin_unarchive:"))
async def unarchive_mission(callback: CallbackQuery, db_session: AsyncSession):
    """Восстановить миссию из архива"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    try:
        mission_id = int(callback.data.split(":")[1])
        
        # Находим миссию
        result = await db_session.execute(
            select(Mission).where(Mission.id == mission_id)
        )
        mission = result.scalar_one_or_none()
        
        if not mission:
            await callback.answer("❌ Миссия не найдена", show_alert=True)
            return
        
        # Восстанавливаем
        mission.is_archived = False
        mission.archived_at = None
        mission.active = True
        
        await db_session.commit()
        
        await callback.answer("✅ Миссия восстановлена", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error unarchiving mission: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)
