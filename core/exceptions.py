#/core/exceptions.py

"""
Кастомные исключения приложения. 
Для удобной обработки ошибок в handlers и services.
"""

from typing import Optional


class MissionBotException(Exception):
    """Базовое исключение для всех ошибок бота"""
    pass


class UserNotFound(MissionBotException):
    """Пользователь не найден в БД"""
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"User {user_id} not found")


class MissionNotFound(MissionBotException):
    """Миссия не найдена в БД"""
    def __init__(self, mission_id: int):
        self.mission_id = mission_id
        super().__init__(f"Mission {mission_id} not found")


class NoChargesLeft(MissionBotException):
    """У пользователя нет зарядов"""
    def __init__(self, user_id:  int):
        self.user_id = user_id
        super().__init__(f"User {user_id} has no charges left")


class InvalidMissionDifficulty(MissionBotException):
    """Неправильный уровень сложности миссии"""
    def __init__(self, difficulty: str, valid_values: list):
        self.difficulty = difficulty
        self.valid_values = valid_values
        super().__init__(
            f"Invalid difficulty '{difficulty}'. Valid values: {valid_values}"
        )


class PairNotFound(MissionBotException):
    """Пара не найдена"""
    def __init__(self, pair_id: Optional[int] = None):
        super().__init__(f"Pair not found" + (f" (id={pair_id})" if pair_id else ""))


class UnauthorizedAccess(MissionBotException):
    """Несанкционированный доступ (не админ и т.д.)"""
    def __init__(self, user_id:  int, action: str):
        super().__init__(f"User {user_id} not authorized for action: {action}")