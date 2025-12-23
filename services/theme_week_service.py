# /services/theme_week_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import random
from models.theme_week import ThemeWeek, UserThemeWeekProgress, ThemeWeekAchievement
from models.mission import Mission
from models.completion import Completion


class ThemeWeekService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def get_active_theme_week(self) -> Optional[ThemeWeek]:
        """Получить активную тематическую неделю"""
        result = await self.db_session.execute(
            select(ThemeWeek).where(
                and_(
                    ThemeWeek.active == True,
                    ThemeWeek.start_date <= datetime.utcnow(),
                    ThemeWeek.end_date >= datetime.utcnow()
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_upcoming_theme_week(self) -> Optional[ThemeWeek]:
        """Получить предстоящую тематическую неделю"""
        result = await self.db_session.execute(
            select(ThemeWeek).where(
                and_(
                    ThemeWeek.active == True,
                    ThemeWeek.start_date > datetime.utcnow()
                )
            ).order_by(ThemeWeek.start_date)
        )
        return result.scalar_one_or_none()
    
    async def get_all_theme_weeks(self) -> List[ThemeWeek]:
        """Получить все тематические недели"""
        result = await self.db_session.execute(
            select(ThemeWeek).order_by(ThemeWeek.start_date.desc())
        )
        return result.scalars().all()
    
    async def create_theme_week(self, theme_name: str, description: str, 
                               start_date: datetime, end_date: datetime, 
                               tags: List[str]) -> ThemeWeek:
        """Создать новую тематическую неделю"""
        theme_week = ThemeWeek(
            theme_name=theme_name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            tags=tags
        )
        
        self.db_session.add(theme_week)
        await self.db_session.commit()
        await self.db_session.refresh(theme_week)
        
        return theme_week
    
    async def get_user_progress(self, user_id: int, theme_week_id: int) -> Optional[UserThemeWeekProgress]:
        """Получить прогресс пользователя по тематической неделе"""
        result = await self.db_session.execute(
            select(UserThemeWeekProgress).where(
                and_(
                    UserThemeWeekProgress.user_id == user_id,
                    UserThemeWeekProgress.theme_week_id == theme_week_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_or_create_user_progress(self, user_id: int, theme_week_id: int) -> UserThemeWeekProgress:
        """Получить или создать прогресс пользователя по тематической неделе"""
        progress = await self.get_user_progress(user_id, theme_week_id)
        
        if not progress:
            progress = UserThemeWeekProgress(
                user_id=user_id,
                theme_week_id=theme_week_id
            )
            self.db_session.add(progress)
            await self.db_session.commit()
            await self.db_session.refresh(progress)
        
        return progress
    
    async def update_user_progress(self, user_id: int, theme_week_id: int, 
                                  points_earned: int = 0, mission_completed: bool = False) -> UserThemeWeekProgress:
        """Обновить прогресс пользователя по тематической неделе"""
        progress = await self.get_or_create_user_progress(user_id, theme_week_id)
        
        if mission_completed:
            progress.missions_completed += 1
        
        progress.total_points += points_earned
        
        # Проверяем, завершена ли неделя (условие: 7 миссий или 100 очков)
        if progress.missions_completed >= 7 or progress.total_points >= 100:
            if not progress.completed_at:
                progress.completed_at = datetime.utcnow()
        
        await self.db_session.commit()
        return progress
    
    async def get_available_theme_missions(self, theme_week: ThemeWeek) -> List[str]:
        """Получить доступные миссии для тематической недели"""
        # В реальном приложении это будет из базы миссий с фильтрацией по тегам
        # Пока используем фиксированные миссии для каждой темы
        theme_missions = {
            "внимательность": [
                "Найди и сфотографируй что-то идеально круглое",
                "Послушай 5 минут тишину и опиши свои ощущения",
                "Обрати внимание на детали в привычном месте",
                "Сфотографируй красивый момент за окном",
                "Заметь, что изменилось в твоей комнате за неделю"
            ],
            "общение": [
                "Поздоровайся с незнакомцем (вежливо)",
                "Напиши комплимент близкому человеку",
                "Позвони старому другу",
                "Сфотографируй момент общения с кем-то",
                "Скажи 'спасибо' кому-то сегодня"
            ],
            "творчество": [
                "Нарисуй что-то за 5 минут",
                "Сделай фото с необычного ракурса",
                "Напиши короткое стихотворение",
                "Создай что-то из подручных материалов",
                "Попробуй новую прическу или образ"
            ],
            "здоровье": [
                "Сделай 10 приседаний",
                "Выпей стакан воды с утра",
                "Сделай утреннюю зарядку",
                "Прогуляйся 15 минут на свежем воздухе",
                "Попробуй новое здоровое блюдо"
            ]
        }
        
        missions = []
        for tag in theme_week.tags:
            if tag in theme_missions:
                missions.extend(theme_missions[tag])
        
        return missions if missions else [
            "Сделай что-то полезное для себя",
            "Посмотри на мир по-новому",
            "Сделай шаг к лучшему настроению",
            "Обрати внимание на свои ощущения",
            "Попробуй что-то новое сегодня"
        ]
    
    async def get_week_achievements(self, theme_week_id: int) -> List[ThemeWeekAchievement]:
        """Получить достижения для тематической недели"""
        result = await self.db_session.execute(
            select(ThemeWeekAchievement).where(
                ThemeWeekAchievement.theme_week_id == theme_week_id
            )
        )
        return result.scalars().all()
    
    async def check_and_award_achievements(self, user_id: int, theme_week_id: int) -> List[ThemeWeekAchievement]:
        """Проверить и начислить достижения пользователю"""
        progress = await self.get_user_progress(user_id, theme_week_id)
        if not progress:
            return []
        
        achievements = await self.get_week_achievements(theme_week_id)
        awarded_achievements = []
        
        for achievement in achievements:
            if achievement.name in progress.achievements:
                continue  # уже получено
            
            # Проверяем условия достижения
            if (achievement.missions_required and progress.missions_completed >= achievement.missions_required) or \
               (achievement.points_required and progress.total_points >= achievement.points_required):
                
                # Добавляем достижение к пользователю
                if not progress.achievements:
                    progress.achievements = []
                progress.achievements.append(achievement.name)
                
                awarded_achievements.append(achievement)
        
        if awarded_achievements:
            await self.db_session.commit()
        
        return awarded_achievements
    
    async def get_leaderboard(self, theme_week_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получить таблицу лидеров для тематической недели"""
        result = await self.db_session.execute(
            select(UserThemeWeekProgress).where(
                UserThemeWeekProgress.theme_week_id == theme_week_id
            ).order_by(
                UserThemeWeekProgress.total_points.desc(),
                UserThemeWeekProgress.missions_completed.desc()
            ).limit(limit)
        )
        progress_records = result.scalars().all()
        
        leaderboard = []
        for i, record in enumerate(progress_records, 1):
            leaderboard.append({
                'position': i,
                'user_id': record.user_id,
                'points': record.total_points,
                'missions_completed': record.missions_completed,
                'completed': record.is_completed()
            })
        
        return leaderboard
    
    async def cleanup_finished_weeks(self):
        """Очистить старые тематические недели"""
        await self.db_session.execute(
            update(ThemeWeek)
            .where(and_(ThemeWeek.end_date < datetime.utcnow(), ThemeWeek.active == True))
            .values(active=False)
        )
        await self.db_session.commit()