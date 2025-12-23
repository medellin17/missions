# handlers/mission_groups.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

from services.mission_group_service import MissionGroupService
from services.user_progress_service import UserProgressService
from services.user_service import UserService
from services.completion_service import CompletionService
from keyboards.group_kb import (
    get_groups_list_keyboard,
    get_group_details_keyboard,
    get_group_mission_keyboard,
    get_group_progress_keyboard,
    get_group_completion_keyboard,
    get_restart_confirmation_keyboard
)
from keyboards.mission_kb import get_back_to_main_keyboard
from models.mission_group import GroupType

logger = logging.getLogger(__name__)
router = Router()


# ========== FSM STATES ==========

class GroupReportStates(StatesGroup):
    waiting_for_text_report = State()
    waiting_for_photo_report = State()


# ========== ПОКАЗ СПИСКА ГРУПП ==========

@router.callback_query(F.data == "show_groups")
async def callback_show_groups(callback: CallbackQuery, db_session):
    """Показать список доступных групп"""
    try:
        user_id = callback.from_user.id
        
        # Получаем доступные группы
        group_service = MissionGroupService(db_session)
        progress_service = UserProgressService(db_session)
        
        groups = await group_service.get_available_groups(user_id)
        
        if not groups:
            await callback.message.edit_text(
                "📭 <b>Нет доступных групп</b>\n\n"
                "Пока нет групп миссий, доступных для вашего уровня.\n"
                "Выполняйте обычные миссии, чтобы повысить уровень!",
                parse_mode="HTML",
                reply_markup=get_back_to_main_keyboard()
            )
            await callback.answer()
            return
        
        # Получаем прогресс пользователя по группам
        user_progress = {}
        for group in groups:
            progress_details = await progress_service.get_progress_details(user_id, group.id)
            if progress_details:
                user_progress[group.id] = progress_details
        
        # Формируем текст
        text = (
            "🎯 <b>Группы миссий</b>\n\n"
            "Выберите группу для прохождения:\n\n"
            "🎲 - Случайный порядок\n"
            "🗺️ - Последовательный квест\n"
        )
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_groups_list_keyboard(groups, user_progress)
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing groups: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ========== ПРОСМОТР ДЕТАЛЕЙ ГРУППЫ ==========

@router.callback_query(F.data.startswith("group_view:"))
async def callback_group_view(callback: CallbackQuery, db_session):
    """Показать детали группы"""
    try:
        group_id = int(callback.data.split(":")[1])
        user_id = callback.from_user.id
        
        group_service = MissionGroupService(db_session)
        progress_service = UserProgressService(db_session)
        
        # Проверяем доступ
        has_access = await group_service.check_group_access(user_id, group_id)
        if not has_access:
            await callback.answer("❌ У вас нет доступа к этой группе", show_alert=True)
            return
        
        # Получаем группу
        group = await group_service.get_group_details(group_id)
        if not group:
            await callback.answer("❌ Группа не найдена", show_alert=True)
            return
        
        # Получаем прогресс
        progress = await progress_service.get_progress_details(user_id, group_id)
        
        # Получаем количество миссий
        total_missions = await group_service.get_group_missions_count(group_id)
        
        # Формируем описание типа
        if group.group_type == GroupType.RANDOM:
            type_desc = "🎲 Случайный порядок"
            type_info = "Миссии выдаются в случайном порядке. Можно выполнять в любой последовательности."
        else:
            type_desc = "🗺️ Последовательный квест"
            type_info = "Миссии нужно выполнять строго по порядку. Каждая миссия - это новая глава истории!"
        
        # Формируем текст
        text = (
            f"{group.emoji} <b>{group.name}</b>\n\n"
            f"{group.description}\n\n"
            f"<b>Тип:</b> {type_desc}\n"
            f"{type_info}\n\n"
            f"<b>Миссий в группе:</b> {total_missions}\n"
        )
        
        if progress:
            completed = progress['completed']
            total = progress['total']
            percentage = progress['percentage']
            is_completed = progress['is_completed']
            
            if is_completed:
                text += (
                    f"\n✅ <b>Группа завершена!</b>\n"
                    f"Заработано очков: {progress['points_earned']}\n"
                )
            else:
                progress_bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
                text += (
                    f"\n📊 <b>Ваш прогресс:</b>\n"
                    f"[{progress_bar}] {percentage}%\n"
                    f"Выполнено: {completed}/{total} миссий\n"
                )
        else:
            text += f"\n🆕 Вы ещё не начали эту группу"
        
        text += f"\n🎁 <b>Бонус за завершение:</b> +{group.completion_bonus} очков"
        
        has_progress = progress and progress['completed'] > 0
        is_completed = progress and progress['is_completed']
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_group_details_keyboard(group_id, has_progress, is_completed)
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error viewing group: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ========== НАЧАЛО МИССИИ ИЗ ГРУППЫ ==========

@router.callback_query(F.data.startswith("group_start:"))
async def callback_group_start(callback: CallbackQuery, db_session):
    """Начать/продолжить миссию из группы"""
    try:
        group_id = int(callback.data.split(":")[1])
        user_id = callback.from_user.id
        
        group_service = MissionGroupService(db_session)
        progress_service = UserProgressService(db_session)
        user_service = UserService(db_session)
        
        # Проверяем доступ
        has_access = await group_service.check_group_access(user_id, group_id)
        if not has_access:
            await callback.answer("❌ У вас нет доступа к этой группе", show_alert=True)
            return
        
        # Проверяем заряды
        user = await user_service.get_or_create_user(user_id)
        user = await user_service.check_and_reset_charges(user)
        
        if user.charges <= 0:
            await callback.answer(
                "⚡ У вас закончились заряды!\n"
                "Заряды восстанавливаются в полночь по МСК.",
                show_alert=True
            )
            return
        
        # Получаем следующую миссию
        mission = await progress_service.get_next_mission(user_id, group_id)
        
        if not mission:
            await callback.answer("✅ Все миссии в группе выполнены!", show_alert=True)
            return
        
        # Получаем группу для отображения типа
        group = await group_service.get_group_details(group_id)
        
        # Тратим заряд
        await user_service.use_charge(user)
        
        # Формируем текст миссии
        if group.group_type == GroupType.SEQUENTIAL:
            progress = await progress_service.get_progress_details(user_id, group_id)
            chapter = progress['completed'] + 1 if progress else 1
            text = (
                f"🗺️ <b>{group.name}</b>\n"
                f"Глава {chapter}\n\n"
                f"<b>Миссия:</b>\n{mission.text}\n\n"
                f"<b>Награда:</b> {mission.points_reward} очков\n"
                f"⚡ Осталось зарядов: {user.charges}/3"
            )
        else:
            text = (
                f"🎲 <b>{group.name}</b>\n\n"
                f"<b>Миссия:</b>\n{mission.text}\n\n"
                f"<b>Награда:</b> {mission.points_reward} очков\n"
                f"⚡ Осталось зарядов: {user.charges}/3"
            )
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_group_mission_keyboard(group_id, mission.id)
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error starting group mission: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ========== ОТПРАВКА ТЕКСТОВОГО ОТЧЁТА ==========

@router.callback_query(F.data.startswith("group_report_text:"))
async def callback_group_report_text(callback: CallbackQuery, state: FSMContext):
    """Начать отправку текстового отчёта"""
    try:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        mission_id = int(parts[2])
        
        await state.set_state(GroupReportStates.waiting_for_text_report)
        await state.update_data(group_id=group_id, mission_id=mission_id)
        
        await callback.message.answer(
            "📝 <b>Текстовый отчёт</b>\n\n"
            "Опишите, как вы выполнили миссию.\n"
            "Напишите ваш отчёт в следующем сообщении.\n\n"
            "Для отмены отправьте /cancel",
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error starting text report: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.message(GroupReportStates.waiting_for_text_report)
async def process_text_report(message: Message, state: FSMContext, db_session):
    """Обработать текстовый отчёт"""
    try:
        if message.text and message.text.startswith('/cancel'):
            await state.clear()
            await message.answer("❌ Отправка отчёта отменена")
            return
        
        data = await state.get_data()
        group_id = data['group_id']
        mission_id = data['mission_id']
        user_id = message.from_user.id
        
        # Сохраняем отчёт
        completion_service = CompletionService(db_session)
        progress_service = UserProgressService(db_session)
        user_service = UserService(db_session)
        group_service = MissionGroupService(db_session)
        
        # Получаем миссию для награды
        from sqlalchemy import select
        from models.mission import Mission
        
        result = await db_session.execute(
            select(Mission).where(Mission.id == mission_id)
        )
        mission = result.scalar_one_or_none()
        
        if not mission:
            await message.answer("❌ Миссия не найдена")
            await state.clear()
            return
        
        # Создаём completion
        await completion_service.create_completion(
            user_id=user_id,
            mission_id=mission_id,
            report_type="text",
            report_content=message.text,
            points_reward=mission.points_reward
        )
        
        # Обновляем прогресс в группе
        await progress_service.update_progress(
            user_id=user_id,
            group_id=group_id,
            mission_id=mission_id,
            points_earned=mission.points_reward
        )
        
        # Начисляем очки пользователю
        user = await user_service.get_or_create_user(user_id)
        old_level = user.level
        user.points += mission.points_reward
        user.level = user.points // 100 + 1
        await db_session.commit()
        
        # Проверяем завершение группы
        progress = await progress_service.get_progress_details(user_id, group_id)
        
        if progress and progress['is_completed']:
            group = await group_service.get_group_details(group_id)
            
            text = (
                f"🎉 <b>ГРУППА ЗАВЕРШЕНА!</b>\n\n"
                f"{group.emoji} <b>{group.name}</b>\n\n"
                f"Поздравляем! Вы завершили все миссии в группе!\n\n"
                f"✨ Получено очков за миссию: +{mission.points_reward}\n"
                f"🎁 Бонус за завершение группы: +{group.completion_bonus}\n"
                f"📊 Всего очков: {user.points}\n"
            )
            
            if user.level > old_level:
                text += f"\n🎊 <b>НОВЫЙ УРОВЕНЬ: {user.level}!</b>"
            
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=get_group_completion_keyboard(group_id)
            )
        else:
            text = (
                f"✅ <b>Миссия выполнена!</b>\n\n"
                f"Получено очков: +{mission.points_reward}\n"
                f"Всего очков: {user.points}\n"
            )
            
            if user.level > old_level:
                text += f"\n🎊 <b>НОВЫЙ УРОВЕНЬ: {user.level}!</b>\n"
            
            if progress:
                text += f"\n📊 Прогресс в группе: {progress['completed']}/{progress['total']}"
            
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=get_group_progress_keyboard(group_id)
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing text report: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при сохранении отчёта")
        await state.clear()


# ========== ОТПРАВКА ФОТО-ОТЧЁТА ==========

@router.callback_query(F.data.startswith("group_report_photo:"))
async def callback_group_report_photo(callback: CallbackQuery, state: FSMContext):
    """Начать отправку фото-отчёта"""
    try:
        parts = callback.data.split(":")
        group_id = int(parts[1])
        mission_id = int(parts[2])
        
        await state.set_state(GroupReportStates.waiting_for_photo_report)
        await state.update_data(group_id=group_id, mission_id=mission_id)
        
        await callback.message.answer(
            "📸 <b>Фото-отчёт</b>\n\n"
            "Отправьте фотографию, подтверждающую выполнение миссии.\n\n"
            "Для отмены отправьте /cancel",
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error starting photo report: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.message(GroupReportStates.waiting_for_photo_report, F.photo)
async def process_photo_report(message: Message, state: FSMContext, db_session):
    """Обработать фото-отчёт"""
    try:
        data = await state.get_data()
        group_id = data['group_id']
        mission_id = data['mission_id']
        user_id = message.from_user.id
        
        # Получаем file_id последнего (самого большого) фото
        photo_file_id = message.photo[-1].file_id
        
        # Сохраняем отчёт (аналогично текстовому)
        completion_service = CompletionService(db_session)
        progress_service = UserProgressService(db_session)
        user_service = UserService(db_session)
        group_service = MissionGroupService(db_session)
        
        # Получаем миссию
        from sqlalchemy import select
        from models.mission import Mission
        
        result = await db_session.execute(
            select(Mission).where(Mission.id == mission_id)
        )
        mission = result.scalar_one_or_none()
        
        if not mission:
            await message.answer("❌ Миссия не найдена")
            await state.clear()
            return
        
        # Создаём completion
        await completion_service.create_completion(
            user_id=user_id,
            mission_id=mission_id,
            report_type="photo",
            report_content=photo_file_id,
            points_reward=mission.points_reward
        )
        
        # Обновляем прогресс
        await progress_service.update_progress(
            user_id=user_id,
            group_id=group_id,
            mission_id=mission_id,
            points_earned=mission.points_reward
        )
        
        # Начисляем очки
        user = await user_service.get_or_create_user(user_id)
        old_level = user.level
        user.points += mission.points_reward
        user.level = user.points // 100 + 1
        await db_session.commit()
        
        # Проверяем завершение
        progress = await progress_service.get_progress_details(user_id, group_id)
        
        if progress and progress['is_completed']:
            group = await group_service.get_group_details(group_id)
            
            text = (
                f"🎉 <b>ГРУППА ЗАВЕРШЕНА!</b>\n\n"
                f"{group.emoji} <b>{group.name}</b>\n\n"
                f"Поздравляем! Вы завершили все миссии в группе!\n\n"
                f"✨ Получено очков за миссию: +{mission.points_reward}\n"
                f"🎁 Бонус за завершение группы: +{group.completion_bonus}\n"
                f"📊 Всего очков: {user.points}\n"
            )
            
            if user.level > old_level:
                text += f"\n🎊 <b>НОВЫЙ УРОВЕНЬ: {user.level}!</b>"
            
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=get_group_completion_keyboard(group_id)
            )
        else:
            text = (
                f"✅ <b>Миссия выполнена!</b>\n\n"
                f"Получено очков: +{mission.points_reward}\n"
                f"Всего очков: {user.points}\n"
            )
            
            if user.level > old_level:
                text += f"\n🎊 <b>НОВЫЙ УРОВЕНЬ: {user.level}!</b>\n"
            
            if progress:
                text += f"\n📊 Прогресс в группе: {progress['completed']}/{progress['total']}"
            
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=get_group_progress_keyboard(group_id)
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing photo report: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при сохранении отчёта")
        await state.clear()


# ========== ПРОСМОТР ПРОГРЕССА ==========

@router.callback_query(F.data.startswith("group_progress:"))
async def callback_group_progress(callback: CallbackQuery, db_session):
    """Показать прогресс в группе"""
    try:
        group_id = int(callback.data.split(":")[1])
        user_id = callback.from_user.id
        
        group_service = MissionGroupService(db_session)
        progress_service = UserProgressService(db_session)
        
        group = await group_service.get_group_details(group_id)
        progress = await progress_service.get_progress_details(user_id, group_id)
        
        if not group or not progress:
            await callback.answer("❌ Данные не найдены", show_alert=True)
            return
        
        completed = progress['completed']
        total = progress['total']
        percentage = progress['percentage']
        points = progress['points_earned']
        
        progress_bar = "█" * int(percentage / 10) + "░" * (10 - int(percentage / 10))
        
        text = (
            f"{group.emoji} <b>{group.name}</b>\n\n"
            f"📊 <b>Ваш прогресс:</b>\n\n"
            f"[{progress_bar}] {percentage}%\n\n"
            f"✅ Выполнено миссий: {completed}/{total}\n"
            f"⭐ Заработано очков: {points}\n"
        )
        
        if progress['is_completed']:
            text += (
                f"\n🎉 <b>Группа завершена!</b>\n"
                f"Завершено: {progress['completed_at'].strftime('%d.%m.%Y %H:%M') if progress['completed_at'] else 'N/A'}"
            )
        else:
            remaining = total - completed
            text += f"\n🎯 Осталось миссий: {remaining}"
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_group_progress_keyboard(group_id)
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing progress: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ========== ПЕРЕЗАПУСК ГРУППЫ ==========

@router.callback_query(F.data.startswith("group_restart:"))
async def callback_group_restart(callback: CallbackQuery):
    """Запрос на перезапуск группы"""
    try:
        group_id = int(callback.data.split(":")[1])
        
        await callback.message.edit_text(
            "🔄 <b>Перезапуск группы</b>\n\n"
            "Вы уверены, что хотите начать группу заново?\n\n"
            "⚠️ Ваш прогресс будет сброшен, но заработанные очки останутся.",
            parse_mode="HTML",
            reply_markup=get_restart_confirmation_keyboard(group_id)
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error restart request: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data.startswith("group_restart_confirm:"))
async def callback_group_restart_confirm(callback: CallbackQuery, db_session):
    """Подтвердить перезапуск группы"""
    try:
        group_id = int(callback.data.split(":")[1])
        user_id = callback.from_user.id
        
        progress_service = UserProgressService(db_session)
        
        # Сбрасываем прогресс
        success = await progress_service.reset_progress(user_id, group_id)
        
        if success:
            await callback.answer("✅ Прогресс сброшен. Можете начать заново!", show_alert=True)
            # Возвращаем к просмотру группы
            await callback_group_view(callback, db_session)
        else:
            await callback.answer("❌ Не удалось сбросить прогресс", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error confirming restart: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ========== ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ==========

@router.callback_query(F.data == "back_to_mission_menu")
async def callback_back_to_mission_menu(callback: CallbackQuery):
    """Вернуться в главное меню миссий"""
    try:
        from keyboards.mission_kb import get_main_menu_keyboard
        
        await callback.message.edit_text(
            "🎯 <b>Главное меню</b>\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error returning to menu: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка", show_alert=True)


# ========== ЗАГЛУШКА ==========

@router.callback_query(F.data == "noop")
async def callback_noop(callback: CallbackQuery):
    """Заглушка для информационных кнопок"""
    await callback.answer()
