"""
期货推荐服务
"""

import logging
import asyncio
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_mongo_db
from app.models.futures import (
    FuturesRecommendation, FuturesRecommendationBatch, EntryRange,
    AnalysisReport, RecommendationStatus, FuturesDirection
)
from app.services.futures_config_service import get_futures_config_service
from tradingagents.dataflows.providers.futures.futures_data_provider import get_futures_data_manager
from app.utils.timezone import now_tz
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("futures_recommendation_service")


class FuturesRecommendationService:
    """期货推荐服务"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.recommendations_collection = db["futures_recommendations"]
        self.batches_collection = db["futures_recommendation_batches"]
        self.config_service = get_futures_config_service()
        self.data_manager = get_futures_data_manager()

    async def generate_recommendations(
        self,
        symbols: Optional[List[str]] = None,
        ai_models: Optional[List[str]] = None,
        custom_prompt: Optional[str] = None
    ) -> FuturesRecommendationBatch:
        """生成期货推荐"""
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now()

        try:
            # 获取配置
            if not symbols:
                symbols = await self.config_service.get_futures_symbols()

            if not ai_models:
                enabled_models = await self.config_service.get_enabled_ai_models()
                ai_models = [model["model"] for model in enabled_models]

            logger.info(f"开始生成推荐 [batch_id={batch_id}]")
            logger.info(f"期货品种: {symbols}")
            logger.info(f"AI模型: {ai_models}")

            # 获取期货数据
            futures_data_list = await self.data_manager.get_multiple_futures_data(symbols)
            logger.info(f"获取到 {len(futures_data_list)} 个期货的数据")

            # 生成推荐
            recommendations = []
            for futures_data in futures_data_list:
                try:
                    recommendation = await self._generate_single_recommendation(
                        futures_data,
                        ai_models,
                        custom_prompt,
                        batch_id
                    )
                    if recommendation:
                        recommendations.append(recommendation)
                except Exception as e:
                    logger.error(f"生成推荐失败 ({futures_data.symbol}): {e}")
                    continue

            # 创建批次
            batch = FuturesRecommendationBatch(
                batch_id=batch_id,
                cycle_time=now_tz(),
                total_recommendations=len(recommendations),
                successful_recommendations=len(recommendations),
                failed_recommendations=len(symbols) - len(recommendations),
                recommendations=recommendations,
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                ai_models_used=ai_models
            )

            # 保存到数据库
            await self._save_batch(batch)
            logger.info(f"推荐生成完成 [batch_id={batch_id}], 共 {len(recommendations)} 个推荐")

            return batch
        except Exception as e:
            logger.error(f"生成推荐失败: {e}", exc_info=True)
            # 返回空批次
            return FuturesRecommendationBatch(
                batch_id=batch_id,
                cycle_time=now_tz(),
                total_recommendations=0,
                successful_recommendations=0,
                failed_recommendations=len(symbols or []),
                recommendations=[],
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                ai_models_used=ai_models or []
            )

    async def _generate_single_recommendation(
        self,
        futures_data,
        ai_models: List[str],
        custom_prompt: Optional[str],
        batch_id: str
    ) -> Optional[FuturesRecommendation]:
        """生成单个期货推荐"""
        try:
            # 获取提示词
            prompts = await self.config_service.get_agent_prompts()
            system_prompt = prompts.get("system_prompt", "")
            user_prompt_template = prompts.get("user_prompt_template", "")

            if custom_prompt:
                user_prompt = custom_prompt
            else:
                user_prompt = user_prompt_template.format(
                    symbol=futures_data.symbol,
                    name=futures_data.name,
                    price=futures_data.price,
                    bid=futures_data.bid,
                    ask=futures_data.ask,
                    volume=futures_data.volume,
                    open_interest=futures_data.open_interest
                )

            # 调用AI模型进行分析
            analysis_results = await self._call_ai_models(
                system_prompt,
                user_prompt,
                ai_models
            )

            # 解析分析结果
            recommendation = await self._parse_analysis_results(
                futures_data,
                analysis_results,
                ai_models,
                batch_id
            )

            return recommendation
        except Exception as e:
            logger.error(f"生成单个推荐失败 ({futures_data.symbol}): {e}")
            return None

    async def _call_ai_models(
        self,
        system_prompt: str,
        user_prompt: str,
        ai_models: List[str]
    ) -> Dict[str, str]:
        """并行调用多个AI模型"""
        tasks = []
        for model in ai_models:
            task = asyncio.create_task(
                self._call_single_ai_model(system_prompt, user_prompt, model)
            )
            tasks.append((model, task))

        results = {}
        for model, task in tasks:
            try:
                result = await asyncio.wait_for(task, timeout=30)
                results[model] = result
            except asyncio.TimeoutError:
                logger.warning(f"AI模型 {model} 调用超时")
                results[model] = None
            except Exception as e:
                logger.error(f"AI模型 {model} 调用失败: {e}")
                results[model] = None

        return results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError))
    )
    async def _call_single_ai_model(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str
    ) -> Optional[str]:
        """调用单个AI模型"""
        try:
            # 这里需要集成实际的LLM调用逻辑
            # 暂时返回模拟数据
            logger.info(f"调用AI模型: {model}")

            # 模拟AI响应
            response = f"""
技术面分析：
- 当前价格处于上升趋势
- 支撑位在3490，阻力位在3530
- 短期看涨

基本面分析：
- 经济数据向好
- 政策面支持

资金面分析：
- 持仓量增加
- 资金流入

多头博弈：
- 看好后市
- 建议继续持有

空头博弈：
- 存在风险
- 建议谨慎

综合建议：
方向：多
入场区间：3500-3510
止盈价：3530
止损价：3490
持仓时间：4小时
"""
            return response
        except Exception as e:
            logger.error(f"调用AI模型 {model} 失败: {e}")
            raise

    async def _parse_analysis_results(
        self,
        futures_data,
        analysis_results: Dict[str, str],
        ai_models: List[str],
        batch_id: str
    ) -> Optional[FuturesRecommendation]:
        """解析AI分析结果"""
        try:
            # 简化处理：从分析结果中提取关键信息
            # 实际应用中应该使用更复杂的解析逻辑

            # 默认推荐
            direction = FuturesDirection.LONG
            entry_min = futures_data.price - 10
            entry_max = futures_data.price + 10
            take_profit = futures_data.price + 30
            stop_loss = futures_data.price - 30
            holding_time = "4小时"
            confidence_score = 0.75

            # 从分析结果中提取信息
            analysis_text = " ".join([v for v in analysis_results.values() if v])

            if "空" in analysis_text or "看跌" in analysis_text:
                direction = FuturesDirection.SHORT

            # 创建推荐对象
            recommendation = FuturesRecommendation(
                recommendation_id=f"rec_{batch_id}_{uuid.uuid4().hex[:8]}",
                batch_id=batch_id,
                futures_symbol=futures_data.symbol,
                futures_name=futures_data.name,
                direction=direction,
                entry_range=EntryRange(min_price=entry_min, max_price=entry_max),
                take_profit=take_profit,
                stop_loss=stop_loss,
                holding_time=holding_time,
                confidence_score=confidence_score,
                ai_models_used=ai_models,
                analysis_reports=AnalysisReport(
                    technical_analysis=analysis_results.get(ai_models[0], ""),
                    summary=analysis_text[:500]
                ),
                status=RecommendationStatus.ACTIVE
            )

            # 保存到数据库
            await self._save_recommendation(recommendation)
            return recommendation
        except Exception as e:
            logger.error(f"解析分析结果失败: {e}")
            return None

    async def _save_recommendation(self, recommendation: FuturesRecommendation) -> bool:
        """保存推荐到数据库"""
        try:
            result = await self.recommendations_collection.insert_one(
                recommendation.model_dump(by_alias=True)
            )
            logger.debug(f"保存推荐: {result.inserted_id}")
            return True
        except Exception as e:
            logger.error(f"保存推荐失败: {e}")
            return False

    async def _save_batch(self, batch: FuturesRecommendationBatch) -> bool:
        """保存批次到数据库"""
        try:
            result = await self.batches_collection.insert_one(
                batch.model_dump(by_alias=True)
            )
            logger.debug(f"保存批次: {result.inserted_id}")
            return True
        except Exception as e:
            logger.error(f"保存批次失败: {e}")
            return False

    async def get_latest_recommendations(
        self,
        limit: int = 5,
        offset: int = 0
    ) -> List[FuturesRecommendationBatch]:
        """获取最新推荐"""
        try:
            batches = await self.batches_collection.find(
                {"status": {"$ne": "deleted"}}
            ).sort("created_at", -1).skip(offset).limit(limit).to_list(None)

            return [FuturesRecommendationBatch(**batch) for batch in batches]
        except Exception as e:
            logger.error(f"获取最新推荐失败: {e}")
            return []

    async def get_batch_by_id(self, batch_id: str) -> Optional[FuturesRecommendationBatch]:
        """根据批次ID获取推荐"""
        try:
            batch = await self.batches_collection.find_one({"batch_id": batch_id})
            if batch:
                return FuturesRecommendationBatch(**batch)
            return None
        except Exception as e:
            logger.error(f"获取批次失败: {e}")
            return None

    async def get_recommendation_history(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[FuturesRecommendation]:
        """获取品种推荐历史"""
        try:
            query = {"futures_symbol": symbol}

            if start_date or end_date:
                date_query = {}
                if start_date:
                    date_query["$gte"] = start_date
                if end_date:
                    date_query["$lte"] = end_date
                query["created_at"] = date_query

            recommendations = await self.recommendations_collection.find(
                query
            ).sort("created_at", -1).limit(limit).to_list(None)

            return [FuturesRecommendation(**rec) for rec in recommendations]
        except Exception as e:
            logger.error(f"获取推荐历史失败: {e}")
            return []

    async def update_recommendation_status(
        self,
        recommendation_id: str,
        status: RecommendationStatus
    ) -> bool:
        """更新推荐状态"""
        try:
            result = await self.recommendations_collection.update_one(
                {"recommendation_id": recommendation_id},
                {
                    "$set": {
                        "status": status.value,
                        "updated_at": now_tz()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"更新推荐状态失败: {e}")
            return False


# 全局服务实例
_futures_recommendation_service: Optional[FuturesRecommendationService] = None


def get_futures_recommendation_service() -> FuturesRecommendationService:
    """获取期货推荐服务实例"""
    global _futures_recommendation_service
    if _futures_recommendation_service is None:
        db = get_mongo_db()
        _futures_recommendation_service = FuturesRecommendationService(db)
    return _futures_recommendation_service


def set_futures_recommendation_service(service: FuturesRecommendationService) -> None:
    """设置期货推荐服务实例"""
    global _futures_recommendation_service
    _futures_recommendation_service = service
