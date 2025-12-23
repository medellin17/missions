# keyboards/group_kb.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List
from models.mission_group import MissionGroup, GroupType, AccessType


def get_groups_list_keyboard(groups: List[MissionGroup], user_progress: dict = None) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком доступных групп
    user_progress: {group_id: {"completed": X, "total": Y, "is_completed": bool}}
    """
    buttons = []
    
    if not groups:
        buttons.append([InlineKeyboardButton(
            text="❌ Нет доступных групп",
            callback_data="noop"
        )])
    else:
        for group in groups:
            # Формируем текст кнопки
            button_text = f"{group.emoji} {group.name}"
            
            # Добавляем прогресс если есть
            if user_progress and group.id in user_progress:
                progress = user_progress[group.id]
                if progress.get("is_completed"):
                    button_text += " ✅"
                else:
                    completed = progress.get("completed", 0)
                    total = progress.get("total", 0)
                    button_text += f" ({completed}/{total})"
            
            # Добавляем иконку типа группы
            if group.group_type == GroupType.SEQUENTIAL:
                button_text = "🗺️ " + button_text
            else:
                button_text = "🎲 " + button_text
            
            # Добавляем замок для приватных/по уровню
            if group.access_type == AccessType.PRIVATE:
                button_text += " 🔒"
            elif group.access_type == AccessType.LEVEL_BASED:
                button_text += f" (Ур.{group.required_level}+)"
            
            buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"group_view:{group.id}"
            )])
    
    # Кнопка назад
    buttons.append([InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_mission_menu"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_group_details_keyboard(group_id: int, has_progress: bool = False, is_completed: bool = False) -> InlineKeyboardMarkup:
    """
    Клавиатура с действиями для конкретной группы
    """
    buttons = []
    
    if is_completed:
        # Группа пройдена - можно начать заново
        buttons.append([InlineKeyboardButton(
            text="🔄 Пройти заново",
            callback_data=f"group_restart:{group_id}"
        )])
    elif has_progress:
        # Есть прогресс - продолжить
        buttons.append([InlineKeyboardButton(
            text="▶️ Продолжить",
            callback_data=f"group_start:{group_id}"
        )])
    else:
        # Новая группа - начать
        buttons.append([InlineKeyboardButton(
            text="🎯 Начать",
            callback_data=f"group_start:{group_id}"
        )])
    
    # Показать прогресс
    buttons.append([InlineKeyboardButton(
        text="📊 Прогресс",
        callback_data=f"group_progress:{group_id}"
    )])
    
    # Назад к списку групп
    buttons.append([InlineKeyboardButton(
        text="🔙 К списку групп",
        callback_data="show_groups"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_group_mission_keyboard(group_id: int, mission_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для миссии из группы
    """
    buttons = [
        [InlineKeyboardButton(
            text="✅ Отправить текстовый отчёт",
            callback_data=f"group_report_text:{group_id}:{mission_id}"
        )],
        [InlineKeyboardButton(
            text="📸 Отправить фото-отчёт",
            callback_data=f"group_report_photo:{group_id}:{mission_id}"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад к группе",
            callback_data=f"group_view:{group_id}"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_group_progress_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для просмотра прогресса
    """
    buttons = [
        [InlineKeyboardButton(
            text="▶️ Продолжить миссии",
            callback_data=f"group_start:{group_id}"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад к группе",
            callback_data=f"group_view:{group_id}"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_group_completion_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура после завершения группы
    """
    buttons = [
        [InlineKeyboardButton(
            text="🔄 Пройти заново",
            callback_data=f"group_restart:{group_id}"
        )],
        [InlineKeyboardButton(
            text="🎯 Другие группы",
            callback_data="show_groups"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="back_to_mission_menu"
        )]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_restart_confirmation_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """
    Подтверждение перезапуска группы
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ Да, начать заново",
                callback_data=f"group_restart_confirm:{group_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=f"group_view:{group_id}"
            )
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
