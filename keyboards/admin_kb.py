# keyboards/admin_kb.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_menu_keyboard():
    """Главное меню админки"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Общая аналитика", callback_data="admin_analytics")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="🎯 Миссии", callback_data="admin_missions")],
        [InlineKeyboardButton(text="🎯 Группы миссий", callback_data="admin_manage_groups")],  # ✅ ДОБАВЛЕНО
        [InlineKeyboardButton(text="👫 Пары", callback_data="admin_pairs")],
        [InlineKeyboardButton(text="📅 Тематические недели", callback_data="admin_themes")],
        [InlineKeyboardButton(text="📈 Полный отчет", callback_data="admin_report")],
        [InlineKeyboardButton(text="🔝 Топ пользователей", callback_data="admin_top_users")],
        [InlineKeyboardButton(text="⚙️ Управление миссиями", callback_data="admin_manage_missions")],
        [InlineKeyboardButton(text="👤 Управление пользователями", callback_data="admin_manage_users")]
    ])
    return keyboard


def get_analytics_menu_keyboard():
    """Меню аналитики"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="🎯 Миссии", callback_data="admin_missions")],
        [InlineKeyboardButton(text="👫 Пары", callback_data="admin_pairs")],
        [InlineKeyboardButton(text="📅 Темы", callback_data="admin_themes")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    return keyboard


def get_user_management_keyboard():
    """Меню управления пользователями"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_find_user")],
        [InlineKeyboardButton(text="📋 Список пользователей", callback_data="admin_list_users:0")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    return keyboard


def get_user_list_keyboard(page: int, total_pages: int, users_count: int):
    """Клавиатура списка пользователей с пагинацией"""
    buttons = []
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_list_users:{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="admin_noop"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"admin_list_users:{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Кнопки действий
    buttons.append([
        InlineKeyboardButton(text="🔍 Поиск", callback_data="admin_find_user"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"admin_list_users:{page}")
    ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage_users")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_user_action_keyboard(user_id: int, is_banned: bool):
    """Клавиатура действий над пользователем"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚫 Заблокировать" if not is_banned else "✅ Разблокировать",
            callback_data=f"admin_toggle_ban:{user_id}"
        )],
        [
            InlineKeyboardButton(text="➕ Добавить очки", callback_data=f"admin_add_points:{user_id}"),
            InlineKeyboardButton(text="➖ Отнять очки", callback_data=f"admin_remove_points:{user_id}")
        ],
        [
            InlineKeyboardButton(text="⚡ Сбросить заряды", callback_data=f"admin_reset_charges:{user_id}"),
            InlineKeyboardButton(text="📊 Статистика", callback_data=f"admin_user_stats:{user_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_list_users:0")]
    ])
    return keyboard
    
# keyboards/admin_kb.py
# ДОБАВИТЬ В КОНЕЦ СУЩЕСТВУЮЩЕГО ФАЙЛА:

def get_group_management_keyboard():
    """Меню управления группами миссий"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список групп", callback_data="admin_groups_list")],
        [InlineKeyboardButton(text="➕ Создать группу", callback_data="admin_group_create")],
        [InlineKeyboardButton(text="📊 Статистика групп", callback_data="admin_groups_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")]
    ])
    return keyboard


def get_groups_list_admin_keyboard(page: int = 0, total_pages: int = 1):
    """Список групп для админа с пагинацией"""
    buttons = []
    
    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_groups_list:{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page+1}/{total_pages}", callback_data="admin_noop"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_groups_list:{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Действия
    buttons.append([
        InlineKeyboardButton(text="➕ Создать", callback_data="admin_group_create"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data=f"admin_groups_list:{page}")
    ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage_groups")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_group_edit_keyboard(group_id: int, is_published: bool = False):
    """Клавиатура редактирования группы"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Опубликовать" if not is_published else "📦 Снять с публикации",
            callback_data=f"admin_group_toggle_publish:{group_id}"
        )],
        [
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_group_edit:{group_id}"),
            InlineKeyboardButton(text="🎯 Миссии", callback_data=f"admin_group_missions:{group_id}")
        ],
        [
            InlineKeyboardButton(text="🔐 Доступ", callback_data=f"admin_group_access:{group_id}"),
            InlineKeyboardButton(text="📊 Статистика", callback_data=f"admin_group_stats:{group_id}")
        ],
        [
            InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"admin_group_delete:{group_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_groups_list:0")]
    ])
    return keyboard


def get_group_missions_keyboard(group_id: int, missions_count: int = 0):
    """Управление миссиями в группе"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"📋 Список миссий ({missions_count})",
            callback_data=f"admin_group_missions_list:{group_id}"
        )],
        [InlineKeyboardButton(
            text="➕ Добавить миссию",
            callback_data=f"admin_group_add_mission:{group_id}"
        )],
        [InlineKeyboardButton(
            text="🔢 Изменить порядок",
            callback_data=f"admin_group_reorder:{group_id}"
        )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_group_view:{group_id}")]
    ])
    return keyboard


def get_group_access_keyboard(group_id: int):
    """Управление доступом к группе"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="➕ Выдать доступ",
            callback_data=f"admin_group_grant_access:{group_id}"
        )],
        [InlineKeyboardButton(
            text="📋 Список пользователей",
            callback_data=f"admin_group_access_list:{group_id}"
        )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_group_view:{group_id}")]
    ])
    return keyboard


def get_delete_confirmation_keyboard(group_id: int):
    """Подтверждение удаления группы"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⚠️ Да, удалить",
            callback_data=f"admin_group_delete_confirm:{group_id}"
        )],
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"admin_group_view:{group_id}"
        )]
    ])
    return keyboard