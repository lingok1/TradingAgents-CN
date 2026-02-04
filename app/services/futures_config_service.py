"""
期货推荐系统配置服务
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_mongo_db
from app.models.futures import FuturesConfig, FuturesDirection
from app.utils.timezone import now_tz

logger = logging.getLogger("futures_config_service")


class FuturesConfigService:
    """期货配置服务"""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["futures_configs"]

    async def get_active_config(self) -> Optional[FuturesConfig]:
        """获取激活的配置"""
        try:
            config_doc = await self.collection.find_one(
                {"is_active": True},
                sort=[("updated_at", -1)]
            )
            if config_doc:
                return FuturesConfig(**config_doc)
            return None
        except Exception as e:
            logger.error(f"获取激活配置失败: {e}")
            return None

    async def get_or_create_default_config(self) -> FuturesConfig:
        """获取或创建默认配置"""
        config = await self.get_active_config()
        if config:
            return config

        # 创建默认配置
        default_config = FuturesConfig(
            config_type="futures_recommendation",
            trading_hours={
                "morning_start": "09:30",
                "morning_end": "11:30",
                "afternoon_start": "13:00",
                "afternoon_end": "15:00",
                "night_start": "21:00",
                "night_end": "23:30"
            },
            ai_models=[
                {
                    "provider": "openai",
                    "model": "gpt-4",
                    "enabled": True,
                    "priority": 1
                },
                {
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "enabled": True,
                    "priority": 2
                }
            ],
            futures_symbols=["IF", "IC", "IH", "T", "TF"],
            agent_prompts={
                "system_prompt": """您是一位专业的期货分析师，具有丰富的期货交易经验。
请基于技术面、基本面、资金面等多个维度对期货品种进行深入分析。
分析结果应该包括：
1. 技术面分析：支撑位、阻力位、趋势判断
2. 基本面分析：相关经济数据、政策影响
3. 资金面分析：持仓量变化、资金流向
4. 多头博弈：看涨方的主要观点
5. 空头博弈：看跌方的主要观点

最后给出明确的交易建议：方向（多/空）、入场区间、止盈价、止损价、建议持仓时间。""",
                "user_prompt_template": """请分析期货品种 {symbol}（{name}）的走势。
当前价格：{price}
买价：{bid}
卖价：{ask}
成交量：{volume}
持仓量：{open_interest}

请提供详细的分析报告和交易建议。"""
            },
            recommendation_interval_minutes=10,
            is_active=True
        )

        # 保存到数据库
        result = await self.collection.insert_one(default_config.model_dump(by_alias=True))
        logger.info(f"创建默认期货配置: {result.inserted_id}")
        return default_config

    async def update_ai_models(self, ai_models: List[Dict[str, Any]]) -> bool:
        """更新AI模型配置"""
        try:
            config = await self.get_active_config()
            if not config:
                logger.error("未找到激活的配置")
                return False

            result = await self.collection.update_one(
                {"_id": config.id},
                {
                    "$set": {
                        "ai_models": ai_models,
                        "updated_at": now_tz()
                    }
                }
            )
            logger.info(f"更新AI模型配置: {result.modified_count} 条记录")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"更新AI模型配置失败: {e}")
            return False

    async def update_futures_symbols(self, symbols: List[str]) -> bool:
        """更新期货品种列表"""
        try:
            config = await self.get_active_config()
            if not config:
                logger.error("未找到激活的配置")
                return False

            result = await self.collection.update_one(
                {"_id": config.id},
                {
                    "$set": {
                        "futures_symbols": symbols,
                        "updated_at": now_tz()
                    }
                }
            )
            logger.info(f"更新期货品种列表: {result.modified_count} 条记录")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"更新期货品种列表失败: {e}")
            return False

    async def update_agent_prompts(self, prompts: Dict[str, str]) -> bool:
        """更新Agent提示词"""
        try:
            config = await self.get_active_config()
            if not config:
                logger.error("未找到激活的配置")
                return False

            result = await self.collection.update_one(
                {"_id": config.id},
                {
                    "$set": {
                        "agent_prompts": prompts,
                        "updated_at": now_tz()
                    }
                }
            )
            logger.info(f"更新Agent提示词: {result.modified_count} 条记录")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"更新Agent提示词失败: {e}")
            return False

    async def update_trading_hours(self, trading_hours: Dict[str, str]) -> bool:
        """更新交易时间配置"""
        try:
            config = await self.get_active_config()
            if not config:
                logger.error("未找到激活的配置")
                return False

            result = await self.collection.update_one(
                {"_id": config.id},
                {
                    "$set": {
                        "trading_hours": trading_hours,
                        "updated_at": now_tz()
                    }
                }
            )
            logger.info(f"更新交易时间配置: {result.modified_count} 条记录")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"更新交易时间配置失败: {e}")
            return False

    async def get_enabled_ai_models(self) -> List[Dict[str, Any]]:
        """获取启用的AI模型列表"""
        try:
            config = await self.get_active_config()
            if not config:
                return []

            # 按优先级排序
            enabled_models = [
                model for model in config.ai_models
                if model.get("enabled", True)
            ]
            enabled_models.sort(key=lambda x: x.get("priority", 999))
            return enabled_models
        except Exception as e:
            logger.error(f"获取启用的AI模型失败: {e}")
            return []

    async def get_trading_hours(self) -> Dict[str, str]:
        """获取交易时间配置"""
        try:
            config = await self.get_active_config()
            if not config:
                return {}
            return config.trading_hours
        except Exception as e:
            logger.error(f"获取交易时间配置失败: {e}")
            return {}

    async def get_futures_symbols(self) -> List[str]:
        """获取期货品种列表"""
        try:
            config = await self.get_active_config()
            if not config:
                return []
            return config.futures_symbols
        except Exception as e:
            logger.error(f"获取期货品种列表失败: {e}")
            return []

    async def get_agent_prompts(self) -> Dict[str, str]:
        """获取Agent提示词"""
        try:
            config = await self.get_active_config()
            if not config:
                return {}
            return config.agent_prompts
        except Exception as e:
            logger.error(f"获取Agent提示词失败: {e}")
            return {}

    async def get_external_data_urls(self) -> List[str]:
        """获取外部数据URL列表"""
        try:
            config = await self.get_active_config()
            if not config:
                return []
            return getattr(config, 'external_data_urls', []) or []
        except Exception as e:
            logger.error(f"获取外部数据URL失败: {e}")
            return []

    async def update_external_data_urls(self, urls: List[str]) -> bool:
        """更新外部数据URL列表"""
        try:
            config = await self.get_active_config()
            if not config:
                logger.error("未找到激活的配置")
                return False

            result = await self.collection.update_one(
                {"_id": config.id},
                {
                    "$set": {
                        "external_data_urls": urls,
                        "updated_at": now_tz()
                    }
                }
            )
            logger.info(f"更新外部数据URL: {result.modified_count} 条记录")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"更新外部数据URL失败: {e}")
            return False


# 全局服务实例
_futures_config_service: Optional[FuturesConfigService] = None


def get_futures_config_service() -> FuturesConfigService:
    """获取期货配置服务实例"""
    global _futures_config_service
    if _futures_config_service is None:
        db = get_mongo_db()
        _futures_config_service = FuturesConfigService(db)
    return _futures_config_service


def set_futures_config_service(service: FuturesConfigService) -> None:
    """设置期货配置服务实例"""
    global _futures_config_service
    _futures_config_service = service
