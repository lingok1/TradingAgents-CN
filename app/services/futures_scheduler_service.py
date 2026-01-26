"""
期货推荐定时任务服务
"""

import logging
from datetime import datetime, time
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_mongo_db
from app.models.futures import SchedulerExecutionRecord
from app.services.futures_recommendation_service import get_futures_recommendation_service
from app.services.futures_config_service import get_futures_config_service
from app.utils.timezone import now_tz

logger = logging.getLogger("futures_scheduler_service")


class FuturesSchedulerService:
    """期货推荐定时任务服务"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.execution_records_collection = db["futures_scheduler_executions"]
        self.recommendation_service = get_futures_recommendation_service()
        self.config_service = get_futures_config_service()

    def is_trading_time(self) -> bool:
        """判断当前是否在交易时间"""
        now = now_tz()
        weekday = now.weekday()  # 0-6, 0=Monday

        # 非工作日（周末）
        if weekday >= 5:  # Saturday=5, Sunday=6
            logger.debug(f"当前是周末，不在交易时间")
            return False

        hour = now.hour
        minute = now.minute
        current_time = time(hour, minute)

        # 日间上午：09:30-11:30
        if time(9, 30) <= current_time < time(11, 30):
            logger.debug(f"当前在日间上午交易时间")
            return True

        # 日间下午：13:00-15:00
        if time(13, 0) <= current_time < time(15, 0):
            logger.debug(f"当前在日间下午交易时间")
            return True

        # 夜盘：21:00-23:30
        if time(21, 0) <= current_time < time(23, 30):
            logger.debug(f"当前在夜盘交易时间")
            return True

        logger.debug(f"当前不在交易时间 ({current_time})")
        return False

    async def execute_recommendation_task(self) -> Optional[str]:
        """执行推荐任务"""
        job_id = "futures_recommendation_scheduler"
        job_name = "期货推荐定时任务"
        start_time = datetime.now()

        try:
            # 检查是否在交易时间
            if not self.is_trading_time():
                logger.info("当前不在交易时间，跳过推荐任务")
                return None

            logger.info(f"开始执行推荐任务")

            # 生成推荐
            batch = await self.recommendation_service.generate_recommendations()

            # 记录执行
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            record = SchedulerExecutionRecord(
                job_id=job_id,
                job_name=job_name,
                batch_id=batch.batch_id,
                status="success",
                scheduled_time=now_tz(),
                execution_time=now_tz(),
                duration_ms=duration_ms,
                total_recommendations=batch.total_recommendations,
                successful_count=batch.successful_recommendations,
                failed_count=batch.failed_recommendations
            )

            await self._save_execution_record(record)
            logger.info(f"推荐任务执行完成 [batch_id={batch.batch_id}]")

            return batch.batch_id
        except Exception as e:
            logger.error(f"推荐任务执行失败: {e}", exc_info=True)

            # 记录失败
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            record = SchedulerExecutionRecord(
                job_id=job_id,
                job_name=job_name,
                status="failed",
                scheduled_time=now_tz(),
                execution_time=now_tz(),
                duration_ms=duration_ms,
                error_message=str(e)
            )

            await self._save_execution_record(record)
            return None

    async def _save_execution_record(self, record: SchedulerExecutionRecord) -> bool:
        """保存执行记录"""
        try:
            result = await self.execution_records_collection.insert_one(
                record.model_dump(by_alias=True)
            )
            logger.debug(f"保存执行记录: {result.inserted_id}")
            return True
        except Exception as e:
            logger.error(f"保存执行记录失败: {e}")
            return False

    async def get_execution_history(
        self,
        job_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """获取执行历史"""
        try:
            records = await self.execution_records_collection.find(
                {"job_id": job_id}
            ).sort("created_at", -1).skip(offset).limit(limit).to_list(None)

            return [SchedulerExecutionRecord(**record) for record in records]
        except Exception as e:
            logger.error(f"获取执行历史失败: {e}")
            return []

    async def get_execution_stats(self, job_id: str) -> dict:
        """获取执行统计"""
        try:
            records = await self.execution_records_collection.find(
                {"job_id": job_id}
            ).to_list(None)

            if not records:
                return {
                    "total_executions": 0,
                    "successful_executions": 0,
                    "failed_executions": 0,
                    "success_rate": 0,
                    "average_duration_ms": 0,
                    "total_recommendations": 0
                }

            total = len(records)
            successful = len([r for r in records if r.get("status") == "success"])
            failed = total - successful

            total_duration = sum(r.get("duration_ms", 0) for r in records)
            avg_duration = total_duration / total if total > 0 else 0

            total_recommendations = sum(r.get("total_recommendations", 0) for r in records)

            return {
                "total_executions": total,
                "successful_executions": successful,
                "failed_executions": failed,
                "success_rate": successful / total if total > 0 else 0,
                "average_duration_ms": avg_duration,
                "total_recommendations": total_recommendations
            }
        except Exception as e:
            logger.error(f"获取执行统计失败: {e}")
            return {}


# 全局服务实例
_futures_scheduler_service: Optional[FuturesSchedulerService] = None


def get_futures_scheduler_service() -> FuturesSchedulerService:
    """获取期货定时任务服务实例"""
    global _futures_scheduler_service
    if _futures_scheduler_service is None:
        db = get_mongo_db()
        _futures_scheduler_service = FuturesSchedulerService(db)
    return _futures_scheduler_service


def set_futures_scheduler_service(service: FuturesSchedulerService) -> None:
    """设置期货定时任务服务实例"""
    global _futures_scheduler_service
    _futures_scheduler_service = service
