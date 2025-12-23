# keyboards/admin_missions_kb.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def missions_manage_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="📃 Список миссий", callback_data="am:list:0:all")],
        [InlineKeyboardButton(text="➕ Создать миссию", callback_data="am:create")],
        [InlineKeyboardButton(text="🔎 Найти по ID", callback_data="am:find")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adminmainmenu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def missions_list_keyboard(page: int, flt: str, has_prev: bool, has_next: bool) -> InlineKeyboardMarkup:
    row = []
    if has_prev:
        row.append(InlineKeyboardButton(text="⬅️", callback_data=f"am:list:{page-1}:{flt}"))
    row.append(InlineKeyboardButton(text="⚙️ Меню", callback_data="am:menu"))
    if has_next:
        row.append(InlineKeyboardButton(text="➡️", callback_data=f"am:list:{page+1}:{flt}"))

    buttons = [
        [
            InlineKeyboardButton(text="Все", callback_data=f"am:list:0:all"),
            InlineKeyboardButton(text="Активные", callback_data=f"am:list:0:active"),
            InlineKeyboardButton(text="Архив", callback_data=f"am:list:0:archived"),
        ],
        row
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def mission_card_keyboard(mission_id: int, is_archived: bool, is_active: bool) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✏️ Текст", callback_data=f"am:edit:text:{mission_id}"),
            InlineKeyboardButton(text="🏷 Теги", callback_data=f"am:edit:tags:{mission_id}"),
        ],
        [
            InlineKeyboardButton(text="🎚 Difficulty", callback_data=f"am:edit:difficulty:{mission_id}"),
            InlineKeyboardButton(text="🎯 Points", callback_data=f"am:edit:points:{mission_id}"),
        ],
        [
            InlineKeyboardButton(
                text=("🚫 Деактивировать" if is_active else "✅ Активировать"),
                callback_data=f"am:toggle:{mission_id}",
            ),
            InlineKeyboardButton(
                text=("♻️ Разархивировать" if is_archived else "🗄 Архивировать"),
                callback_data=f"am:archive:{mission_id}",
            ),
        ],
        [
            InlineKeyboardButton(text="📦 В группу / убрать", callback_data=f"am:edit:group:{mission_id}"),
            InlineKeyboardButton(text="↕️ Порядок (seq)", callback_data=f"am:edit:order:{mission_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"am:delete_confirm:{mission_id}"),
            InlineKeyboardButton(text="⬅️ К списку", callback_data="am:list:0:all"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def delete_confirm_keyboard(mission_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"am:delete:{mission_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"am:view:{mission_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
