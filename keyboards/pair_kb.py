# /keyboards/pair_kb.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List
from models.pair import PairRequest  # Исправлен импорт - PairRequest находится в models.pair


def get_pair_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для меню пары"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🤝 Создать пару", callback_data="create_pair")
    builder.button(text="📋 Заявки", callback_data="view_requests")
    builder.button(text="❌ Покинуть пару", callback_data="leave_pair")
    builder.button(text="🏠 Назад", callback_data="back_to_main")
    
    builder.adjust(2)
    
    return builder.as_markup()


def get_pair_requests_keyboard(requests: List[PairRequest]) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра заявок"""
    builder = InlineKeyboardBuilder()
    
    for request in requests:
        builder.button(
            text=f"👤 @{request.from_user_id}",
            callback_data=f"request_{request.from_user_id}"
        )
    
    builder.button(text="🏠 Назад", callback_data="back_to_main")
    builder.adjust(1, 1)
    
    return builder.as_markup()


def get_request_actions_keyboard(from_user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для действий с заявкой"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="✅ Принять", callback_data=f"accept_request_{from_user_id}")
    builder.button(text="❌ Отклонить", callback_data=f"decline_request_{from_user_id}")
    
    builder.adjust(2)
    
    return builder.as_markup()