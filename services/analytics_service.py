# services/analytics_service.py

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.analytics import AdminAnalytics, BotPerformance, UserActivityLog
from models.completion import Completion
from models.pair import Pair
from models.theme_week import UserThemeWeekProgress
from models.user import User


class AnalyticsService:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.logger = logging.getLogger(__name__)

    async def log_user_activity(
        self,
        user_id: int,
        action: str,
        action_details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Логировать активность пользователя."""
        activity_log = UserActivityLog(
            user_id=user_id,
            action=action,
            action_details=json.dumps(action_details) if action_details else None,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db_session.add(activity_log)
        await self.db_session.commit()

    async def get_daily_active_users(self, days: int = 30) -> List[Dict[str, Any]]:
        """Количество активных пользователей по дням."""
        start_date = datetime.utcnow() - timedelta(days=days)

        result = await self.db_session.execute(
            select(
                func.date(UserActivityLog.timestamp).label("date"),
                func.count(func.distinct(UserActivityLog.user_id)).label("active_users"),
            )
            .where(UserActivityLog.timestamp >= start_date)
            .group_by(func.date(UserActivityLog.timestamp))
            .order_by(asc(func.date(UserActivityLog.timestamp)))
        )

        return [{"date": row.date.isoformat(), "active_users": row.active_users} for row in result.all()]

    async def get_mission_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Статистика миссий: просмотры, выполнения, success rate, среднее время выполнения."""
        start_date = datetime.utcnow() - timedelta(days=days)

        # Просмотры миссий (requests)
        mission_views = await self.db_session.execute(
            select(func.count(UserActivityLog.id)).where(
                and_(
                    UserActivityLog.action == "mission_viewed",
                    UserActivityLog.timestamp >= start_date,
                )
            )
        )
        requests = mission_views.scalar_one() or 0

        # Выполнения миссий (completions)
        mission_completions = await self.db_session.execute(
            select(func.count(Completion.id)).where(Completion.completed_at >= start_date)
        )
        completions = mission_completions.scalar_one() or 0

        success_rate = (completions / requests * 100) if requests > 0 else 0.0

        # Среднее время выполнения (в часах) между mission_viewed и completion (в пределах последних 24 часов до completion)
        avg_completion_time_result = await self.db_session.execute(
            select(
                func.avg(func.extract("epoch", (Completion.completed_at - UserActivityLog.timestamp)) / 3600.0)
            )
            .select_from(Completion)
            .join(
                UserActivityLog,
                and_(
                    UserActivityLog.user_id == Completion.telegram_user_id,
                    UserActivityLog.action == "mission_viewed",
                    UserActivityLog.timestamp <= Completion.completed_at,
                    UserActivityLog.timestamp >= (Completion.completed_at - timedelta(hours=24)),
                ),
            )
            .where(Completion.completed_at >= start_date)
        )
        avg_completion_time_hours = avg_completion_time_result.scalar_one_or_none() or 0.0

        return {
            "requests": requests,
            "completions": completions,
            "success_rate": round(float(success_rate), 2),
            "avg_completion_time_hours": round(float(avg_completion_time_hours), 2),
        }

    async def get_user_growth(self) -> Dict[str, Any]:
        """Рост пользователей."""
        total_users_result = await self.db_session.execute(select(func.count(User.id)))
        total_users = total_users_result.scalar_one() or 0

        new_users_today_result = await self.db_session.execute(
            select(func.count(User.id)).where(func.date(User.created_at) == func.date(datetime.utcnow()))
        )
        new_users_today = new_users_today_result.scalar_one() or 0

        new_users_week_result = await self.db_session.execute(
            select(func.count(User.id)).where(User.created_at >= (datetime.utcnow() - timedelta(days=7)))
        )
        new_users_week = new_users_week_result.scalar_one() or 0

        return {
            "total_users": total_users,
            "new_today": new_users_today,
            "new_this_week": new_users_week,
        }

    async def get_pair_statistics(self) -> Dict[str, Any]:
        """Статистика пар."""
        total_pairs_result = await self.db_session.execute(
            select(func.count(Pair.id)).where(Pair.active == True)
        )
        total_active_pairs = total_pairs_result.scalar_one() or 0

        pair_requests_result = await self.db_session.execute(
            select(func.count(UserActivityLog.id)).where(UserActivityLog.action == "pair_request")
        )
        total_requests = pair_requests_result.scalar_one() or 0

        pair_acceptances_result = await self.db_session.execute(
            select(func.count(UserActivityLog.id)).where(UserActivityLog.action == "pair_accept")
        )
        total_acceptances = pair_acceptances_result.scalar_one() or 0

        acceptance_rate = (total_acceptances / total_requests * 100) if total_requests > 0 else 0.0

        return {
            "total_active_pairs": total_active_pairs,
            "total_requests": total_requests,
            "total_acceptances": total_acceptances,
            "acceptance_rate": round(float(acceptance_rate), 2),
        }

    async def get_theme_week_statistics(self) -> Dict[str, Any]:
        """Статистика тематических недель."""
        participants_result = await self.db_session.execute(
            select(func.count(func.distinct(UserThemeWeekProgress.user_id)))
        )
        total_participants = participants_result.scalar_one() or 0

        avg_progress_result = await self.db_session.execute(
            select(func.avg(UserThemeWeekProgress.missions_completed))
        )
        avg_missions_completed = avg_progress_result.scalar_one_or_none() or 0.0

        completed_result = await self.db_session.execute(
            select(func.count(UserThemeWeekProgress.id)).where(UserThemeWeekProgress.completed_at.is_not(None))
        )
        completed_weeks = completed_result.scalar_one() or 0

        total_progress_result = await self.db_session.execute(select(func.count(UserThemeWeekProgress.id)))
        total_progress = total_progress_result.scalar_one() or 0

        completion_rate = (completed_weeks / total_progress * 100) if total_progress > 0 else 0.0

        return {
            "total_participants": total_participants,
            "avg_missions_completed": round(float(avg_missions_completed), 2),
            "completion_rate": round(float(completion_rate), 2),
            "completed_weeks": completed_weeks,
        }

    async def get_retention_rates(self) -> Dict[str, float]:
        """Удержание 1d (сколько из вчерашних были активны и сегодня)."""
        today = datetime.utcnow().date()

        users_yesterday_result = await self.db_session.execute(
            select(func.count(func.distinct(UserActivityLog.user_id))).where(
                func.date(UserActivityLog.timestamp) == (today - timedelta(days=1))
            )
        )
        users_yesterday = users_yesterday_result.scalar_one() or 0

        try:
            subquery = (
                select(UserActivityLog.user_id)
                .where(func.date(UserActivityLog.timestamp).in_([today, today - timedelta(days=1)]))
                .group_by(UserActivityLog.user_id)
                .having(func.count(func.distinct(func.date(UserActivityLog.timestamp))) == 2)
                .subquery()
            )
            retained_users_result = await self.db_session.execute(select(func.count()).select_from(subquery))
            retained_users = retained_users_result.scalar_one_or_none() or 0
        except Exception:
            retained_users = 0

        retention_1d = (retained_users / users_yesterday * 100) if users_yesterday > 0 else 0.0
        return {"1d_retention": round(float(retention_1d), 2)}

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Метрики бота (среднее за 24 часа)."""
        since = datetime.utcnow() - timedelta(hours=24)

        avg_response_time_result = await self.db_session.execute(
            select(func.avg(BotPerformance.value)).where(
                and_(BotPerformance.metric_type == "response_time", BotPerformance.timestamp >= since)
            )
        )
        avg_response_time_val = avg_response_time_result.scalar_one_or_none() or 0.0

        error_rate_result = await self.db_session.execute(
            select(func.avg(BotPerformance.value)).where(
                and_(BotPerformance.metric_type == "error_rate", BotPerformance.timestamp >= since)
            )
        )
        error_rate_val = error_rate_result.scalar_one_or_none() or 0.0

        return {
            "avg_response_time": round(float(avg_response_time_val), 3),
            "error_rate": round(float(error_rate_val), 2),
        }

    async def get_top_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Топ пользователей по количеству событий в логах."""
        result = await self.db_session.execute(
            select(
                UserActivityLog.user_id,
                func.count(UserActivityLog.id).label("activity_count"),
                func.max(UserActivityLog.timestamp).label("last_activity"),
            )
            .group_by(UserActivityLog.user_id)
            .order_by(desc("activity_count"))
            .limit(limit)
        )

        rows = result.all()
        return [
            {
                "user_id": row.user_id,
                "activity_count": row.activity_count,
                "last_activity": row.last_activity.isoformat() if row.last_activity else None,
            }
            for row in rows
        ]

    async def get_user_engagement(self) -> Dict[str, Any]:
        """Вовлечённость: активные за 24ч/7д + среднее число действий в день."""
        today = datetime.utcnow().date()

        day_subquery = (
            select(
                UserActivityLog.user_id,
                func.count(UserActivityLog.id).label("activity_count"),
            )
            .where(func.date(UserActivityLog.timestamp) == today)
            .group_by(UserActivityLog.user_id)
            .subquery()
        )

        avg_daily_actions_result = await self.db_session.execute(select(func.avg(day_subquery.c.activity_count)))
        avg_daily_actions = avg_daily_actions_result.scalar_one_or_none() or 0.0

        active_24h_result = await self.db_session.execute(
            select(func.count(func.distinct(UserActivityLog.user_id))).where(
                UserActivityLog.timestamp >= (datetime.utcnow() - timedelta(hours=24))
            )
        )
        active_24h = active_24h_result.scalar_one() or 0

        active_7d_result = await self.db_session.execute(
            select(func.count(func.distinct(UserActivityLog.user_id))).where(
                UserActivityLog.timestamp >= (datetime.utcnow() - timedelta(days=7))
            )
        )
        active_7d = active_7d_result.scalar_one() or 0

        total_users = (await self.get_user_growth())["total_users"]
        active_ratio_7d = (active_7d / total_users * 100) if total_users > 0 else 0.0

        return {
            "avg_daily_actions_per_user": round(float(avg_daily_actions), 2),
            "active_24h": active_24h,
            "active_7d": active_7d,
            "active_ratio_7d": round(float(active_ratio_7d), 2),
        }

    async def generate_analytics_report(self) -> Dict[str, Any]:
        """Сгенерировать полный аналитический отчёт."""
        user_growth = await self.get_user_growth()
        mission_stats = await self.get_mission_statistics()
        pair_stats = await self.get_pair_statistics()
        theme_week_stats = await self.get_theme_week_statistics()
        retention_rates = await self.get_retention_rates()
        performance = await self.get_performance_metrics()
        engagement = await self.get_user_engagement()
        top_users = await self.get_top_users(5)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "user_growth": user_growth,
            "mission_stats": mission_stats,
            "pair_stats": pair_stats,
            "theme_week_stats": theme_week_stats,
            "retention_rates": retention_rates,
            "performance": performance,
            "engagement": engagement,
            "top_users": top_users,
        }