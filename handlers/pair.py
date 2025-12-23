# /handlers/pair.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import Optional
import logging
from datetime import datetime
from services.user_service import UserService
from services.pair_service import PairService
from services.mission_service import MissionService
from keyboards.pair_kb import get_pair_menu_keyboard, get_pair_requests_keyboard, get_request_actions_keyboard
from models.user import User
from core.database import get_db_session


router = Router()
logger = logging.getLogger(__name__)


class PairStates(StatesGroup):
    waiting_for_partner_id = State()
    waiting_for_pair_mission_report = State()


@router.message(Command("pair"))
async def cmd_pair(message: Message, db_session):
    """Меню парных миссий"""
    pair_service = PairService(db_session)
    
    # Проверяем, есть ли у пользователя активная пара
    active_pair = await pair_service.get_active_pair(message.from_user.id)
    
    if active_pair:
        partner_id = active_pair.get_partner_id(message.from_user.id)
        await message.answer(
            f"🤝 *Вы в паре с пользователем {partner_id}*\n\n"
            f"Доступные команды:\n"
            f"• /pair_mission - получить парную миссию\n"
            f"• /pair_done - отправить отчет о парной миссии\n"
            f"• /leave_pair - покинуть пару",
            parse_mode="Markdown",
            reply_markup=get_pair_menu_keyboard()
        )
    else:
        await message.answer(
            f"🤝 *Меню парных миссий*\n\n"
            f"• /create_pair - создать пару с другом\n"
            f"• /pair_requests - посмотреть заявки\n"
            f"• /pair_help - справка по парным миссиям",
            parse_mode="Markdown",
            reply_markup=get_pair_menu_keyboard()
        )


@router.message(Command("create_pair"))
async def cmd_create_pair(message: Message, state: FSMContext):
    """Начать создание пары"""
    await message.answer("Введите ID пользователя, с которым хотите создать пару (ID можно получить через /my_id):")
    await state.set_state(PairStates.waiting_for_partner_id)


@router.message(PairStates.waiting_for_partner_id)
async def process_partner_id(message: Message, db_session, state: FSMContext):
    """Обработать ID партнера"""
    try:
        partner_id = int(message.text.strip())
        
        if partner_id == message.from_user.id:
            await message.answer("❌ Нельзя создать пару с самим собой!")
            await state.clear()
            return
        
        pair_service = PairService(db_session)
        
        # Проверяем, не существует ли уже активной пары
        existing_pair = await pair_service.get_active_pair(message.from_user.id)
        if existing_pair:
            await message.answer("❌ Вы уже состоите в активной паре!")
            await state.clear()
            return
        
        # Создаем запрос на пару
        success = await pair_service.create_pair_request(message.from_user.id, partner_id)
        
        if success:
            await message.answer(f"✅ Запрос на создание пары отправлен пользователю {partner_id}")
        else:
            await message.answer("❌ Не удалось создать запрос. Возможно, запрос уже существует или у одного из вас уже есть пара.")
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректный ID пользователя (число).")
    except Exception as e:
        logger.error(f"Error in process_partner_id: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте снова.")
        await state.clear()


@router.message(Command("pair_requests"))
async def cmd_pair_requests(message: Message, db_session):
    """Просмотреть заявки на пару"""
    pair_service = PairService(db_session)
    
    # Получаем заявки, отправленные пользователю
    requests = await pair_service.get_pending_requests_to_user(message.from_user.id)
    
    if not requests:
        await message.answer("📭 Нет новых заявок на создание пары.")
        return
    
    # Отправляем список заявок
    requests_text = "📋 *Заявки на создание пары:*\n\n"
    for request in requests:
        requests_text += f"👤 От: {request.from_user_id}\n"
    
    await message.answer(requests_text, parse_mode="Markdown", reply_markup=get_pair_requests_keyboard(requests))


@router.message(Command("my_id"))
async def cmd_my_id(message: Message):
    """Показать ID пользователя"""
    await message.answer(f"🆔 Ваш ID: `{message.from_user.id}`", parse_mode="Markdown")


@router.message(Command("pair_mission"))
async def cmd_pair_mission(message: Message, db_session):
    """Получить парную миссию"""
    pair_service = PairService(db_session)
    mission_service = MissionService(db_session)
    
    # Проверяем, есть ли активная пара
    active_pair = await pair_service.get_active_pair(message.from_user.id)
    if not active_pair:
        await message.answer("❌ Вы не состоите в активной паре. Используйте /create_pair для создания пары.")
        return
    
    # Проверяем, есть ли уже активная парная миссия
    active_pair_mission = await mission_service.get_active_pair_mission(active_pair.id)
    if active_pair_mission:
        await message.answer(f"🎯 *Текущая парная миссия:*\n\n{active_pair_mission.mission_text}")
        return
    
    # Создаем новую парную миссию
    new_pair_mission = await mission_service.create_pair_mission(active_pair.id)
    if new_pair_mission:
        await message.answer(f"🎯 *Новая парная миссия:*\n\n{new_pair_mission.mission_text}\n\nВыполните миссию и отправьте отчет командой /pair_done")
    else:
        await message.answer("❌ Не удалось создать парную миссию. Попробуйте позже.")


@router.message(Command("pair_done"))
async def cmd_pair_done(message: Message, db_session, state: FSMContext):
    """Отправить отчет о парной миссии"""
    pair_service = PairService(db_session)
    mission_service = MissionService(db_session)
    
    # Проверяем, есть ли активная пара
    active_pair = await pair_service.get_active_pair(message.from_user.id)
    if not active_pair:
        await message.answer("❌ Вы не состоите в активной паре.")
        return
    
    # Получаем активную парную миссию
    active_pair_mission = await mission_service.get_active_pair_mission(active_pair.id)
    if not active_pair_mission:
        await message.answer("❌ Нет активной парной миссии. Получите новую командой /pair_mission")
        return
    
    # Обрабатываем отчет
    report_content = ""
    if message.photo:
        report_content = message.photo[-1].file_id
    elif message.text and message.text != "/pair_done":
        report_content = message.text.replace("/pair_done", "").strip()
    elif message.caption:
        report_content = message.caption.strip()
    else:
        await message.answer("❌ Пожалуйста, пришлите фото или текстовый отчет о выполнении парной миссии.")
        return
    
    # Отмечаем выполнение
    success = await mission_service.mark_pair_mission_completed(active_pair_mission.id, message.from_user.id, report_content)
    
    if success:
        # Проверяем, выполнена ли миссия обоими
        updated_mission = await mission_service.get_active_pair_mission(active_pair.id)
        
        if updated_mission and not updated_mission.active:
            # Миссия выполнена обоими - начисляем очки
            user_service = UserService(db_session)
            user = await user_service.get_or_create_user(message.from_user.id)
            user = await user_service.add_points(user, 15)  # 15 очков за парную миссию
            
            partner_id = active_pair.get_partner_id(message.from_user.id)
            partner_user = await user_service.get_or_create_user(partner_id)
            await user_service.add_points(partner_user, 15)
            
            await message.answer("✅ Парная миссия выполнена! +15 очков каждому участнику.")
        else:
            await message.answer("✅ Ваша часть парной миссии засчитана. Ждем выполнения от партнера.")
    else:
        await message.answer("❌ Не удалось засчитать выполнение миссии.")


@router.message(Command("leave_pair"))
async def cmd_leave_pair(message: Message, db_session):
    """Покинуть пару"""
    pair_service = PairService(db_session)
    
    success = await pair_service.remove_pair(message.from_user.id)
    
    if success:
        await message.answer("✅ Вы покинули пару.")
    else:
        await message.answer("❌ Вы не состоите в активной паре.")


@router.message(Command("pair_help"))
async def cmd_pair_help(message: Message):
    """Справка по парным миссиям"""
    help_text = """
🤝 *Справка по парным миссиям:*

• /create_pair - создать пару с другом (нужен его ID)
• /my_id - получить ваш ID для передачи другу
• /pair_requests - посмотреть заявки на пару
• /pair_mission - получить парную миссию
• /pair_done - отправить отчет о выполнении
• /leave_pair - покинуть пару

💡 *Как это работает:*
- Создайте пару с другом через /create_pair
- Получайте связанные миссии командой /pair_mission
- Выполняйте миссии вместе и получайте +15 очков за каждую
- Парные миссии действуют 24 часа
"""
    
    await message.answer(help_text, parse_mode="Markdown", reply_markup=get_pair_menu_keyboard())


# Callback хендлеры для кнопок
@router.callback_query(F.data == "create_pair")
async def callback_create_pair(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки создания пары"""
    await cmd_create_pair(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "view_requests")
async def callback_view_requests(callback: CallbackQuery, db_session):
    """Обработка кнопки просмотра заявок"""
    await cmd_pair_requests(callback.message, db_session)
    await callback.answer()


@router.callback_query(F.data == "leave_pair")
async def callback_leave_pair(callback: CallbackQuery, db_session):
    """Обработка кнопки покинуть пару"""
    await cmd_leave_pair(callback.message, db_session)
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    from keyboards.mission_kb import get_main_menu_keyboard
    await callback.message.edit_text("🏠 *Главное меню*", reply_markup=get_main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("request_"))
async def callback_view_request(callback: CallbackQuery, db_session):
    """Просмотр конкретной заявки"""
    from_user_id = int(callback.data.split("_")[1])
    
    pair_service = PairService(db_session)
    requests = await pair_service.get_pending_requests_to_user(callback.from_user.id)
    
    # Проверяем, есть ли такая заявка
    request = next((r for r in requests if r.from_user_id == from_user_id), None)
    if not request:
        await callback.answer("❌ Заявка не найдена или уже обработана.", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"👤 Заявка от: {from_user_id}\n\n"
        f"Что хотите сделать?",
        reply_markup=get_request_actions_keyboard(from_user_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("accept_request_"))
async def callback_accept_request(callback: CallbackQuery, db_session):
    """Принять заявку на пару"""
    from_user_id = int(callback.data.split("_")[2])
    
    pair_service = PairService(db_session)
    success = await pair_service.accept_pair_request(callback.from_user.id, from_user_id)
    
    if success:
        await callback.message.edit_text(f"✅ Заявка от {from_user_id} принята! Теперь вы в паре.")
        
        # Попробуем отправить сообщение другому пользователю (если бот его видел)
        try:
            from aiogram import Bot
            from core.config import settings
            bot = Bot(token=settings.BOT_TOKEN)
            await bot.send_message(from_user_id, f"🤝 Ваш запрос на создание пары с {callback.from_user.id} принят!")
        except:
            pass  # Игнорируем ошибку, если не можем отправить сообщение
    else:
        await callback.message.edit_text("❌ Не удалось принять заявку. Возможно, она уже обработана.")
    
    await callback.answer()


@router.callback_query(F.data.startswith("decline_request_"))
async def callback_decline_request(callback: CallbackQuery, db_session):
    """Отклонить заявку на пару"""
    from_user_id = int(callback.data.split("_")[2])
    
    pair_service = PairService(db_session)
    success = await pair_service.decline_pair_request(callback.from_user.id, from_user_id)
    
    if success:
        await callback.message.edit_text(f"❌ Заявка от {from_user_id} отклонена.")
    else:
        await callback.message.edit_text("❌ Не удалось отклонить заявку.")
    
    await callback.answer()