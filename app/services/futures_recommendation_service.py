"""
期货推荐服务
"""

import logging
import asyncio
import uuid
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
import httpx
import pytz

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

# 提示词模板
FUTURES_PROMPT_TEMPLATE = """# 简介
- Name: 实时在中国期货市场挑选5个期货盈利品种
- Description: 根据东方财富期货的宏观经济和期货品种价格的json数据挑选尽可能获得盈利的品种，明确做多做空方向。
- Author: lingqi
- Language: 中文


# 技能：
1.我是一名中国期货市场的专家，有多年的实盘经验，连续10年盈利，我需要你帮我挑选5个期货品种，明确做多做空方向。
2.请一步一步仔细全面深度思考，从多方面分析，尽可能确保我可以盈利。

## 规则
1.仔细分析提供的数据和规则，确保每个步骤都符合要求。
2.从市场趋势入手，了解当前哪些期货品种处于上升或下降趋势中。
3.以下几个方面进行分析：
技术分析：查看这些品种的技术指标，如MACD、RSI、KDJ、BOLL等，压力位、阻力位、支撑位等技术指标，以确认趋势的强度。
基本面分析：考虑供需关系、政策影响等基本面因素。
市场情绪：关注市场情绪和投资者信心。
新闻分析：分析相关新闻、公告和市场事件的影响。
社媒分析：分析社交媒体情绪、投资者心理和舆论导向。
4.根据博弈论分别给出多头和空头的逻辑。
5.告诉我品种价格入场区间，止盈和止损区间。
6.最后生成汇总表格（汇总表格标题的右边显示当前的时间，时间格式为{table_time_format}），要方便阅读，表格显示在输出内容最后而不是中间和前面。
表头品种（代码）显示例如沪银(ag2602)、	生猪(lh2601)。
表格表头为：序号	品种（代码）	多空 建议持仓时间	入场区间	止损	止盈	博弈多头逻辑 博弈空头逻辑	技术要点 基本面要点 市场情绪 资金流入 资金流出 多单持仓量变化 空单持仓量变化

## 下面是东方财富最新json数据和字段说明
0.json数据字段说明：
dm	合约代码（Contract Code），如 USDCNH 表示美元兑离岸人民币合约代码，如"jm2601"
name	合约名称（Contract Name），如"美元兑离岸人民币" 为具体品种名称，合约全称（如"焦煤2601"）
h	最高价（High Price），当日最高成交价格
l	最低价（Low Price），当日最低成交价格
o	开盘价（Open Price），当日开盘价格
p	最新价（Last Price），当前最新成交价格
zf	涨跌幅百分比（不带%符号）（Amplitude），计算公式：(最高价 - 最低价) / 前收盘价 × 100%
zdf	涨跌幅（Change Percentage），计算公式：(最新价 - 前收盘价) / 前收盘价 × 100%
zde 涨跌额（Change Amount），计算公式：最新价 - 前收盘价
zjsj 前收盘价（Previous Close Price），前一交易日的收盘价格
vol	成交量（Volume），当日累计成交数量（单位因品种而异）
ccl	持仓量（Open Interest），当日累计未平仓合约数量
uid	唯一标识符（Unique ID），格式为 `市场代码	合约代码（如 CNYOFFS	USDCNH`）
cje	成交额（Turnover），当日累计成交金额（单位通常为元，未统计时显示 -）
rz	日增仓，当日持仓变化量（正数表示增仓，负数表示减仓，单位：手）
tjd	投机度 成交量/持仓量的比值（反映市场投机活跃度）
dt	未明确（可能为跌停价或其他辅助字段，部分数值与计算相关但未验证）

1.宏观经济的json数据（用于了解宏观经济现状和分析市场，挑选期货时需要排除，切记不要在挑选品种时选用这些数据）：
json数据：
{macro_economic_data}

2.期货品种的价格json数据（仅在这些数据中挑选期货品种）:
json数据：
{futures_price_data}

## 注意事项
- 切记当前时间为 {current_time}（北京时间），我将要在今天 {entry_time} 前开仓。
- 请仔细思考，一步一步思考，再思考，反复思考，深度思考，确保尽可能较高概率盈利。
"""


# 默认外部数据URL
DEFAULT_EXTERNAL_URLS = [
    "https://futsseapi.eastmoney.com/list/custom/CNYOFFS_USDCNH,UDI_UDI,COMEX_GC00Y,NYMEX_CL00Y,EFI_EMFI,CFFEX_IFM,US4_DJIA,SGX_CN00Y,CFFEX_IM2603,SHFE_ag2602,CZCE_UR601,SHFE_fu2601,SHFE_cu2601?orderBy=&sort=&pageSize=999&pageIndex=0&specificContract=true&platform=zbPC&field=name,p,zdf,vol,ccl,rz,tjd,cje,zde,o,h,l,zf,zjsj,zt,dt,dm,sc,tag,uid,zsjd",
    "https://futsseapi.eastmoney.com/list/trans/block/risk/mk0830?orderBy=&sort=&pageSize=999&pageIndex=0&specificContract=true&platform=zbPC&field=name,p,zdf,vol,ccl,rz,tjd,cje,zde,o,h,l,zf,zjsj,zt,dt,dm,sc,tag,uid,zsjd"
]


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
        custom_prompt: Optional[str] = None,
        external_urls: Optional[List[str]] = None
    ) -> FuturesRecommendationBatch:
        """
        生成期货推荐

        流程：
        1. 调用 generate_prompt 获取完整提示词
        2. 将提示词发送给 AI API 接口
        3. 解析 AI 返回结果生成推荐
        """
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now()

        try:
            # 获取AI模型配置
            if not ai_models:
                enabled_models = await self.config_service.get_enabled_ai_models()
                ai_models = [model["model"] for model in enabled_models]

            logger.info(f"开始生成推荐 [batch_id={batch_id}]")
            logger.info(f"AI模型: {ai_models}")

            # 1. 调用 generate_prompt 获取完整提示词
            if custom_prompt:
                user_prompt = custom_prompt
                logger.info("使用自定义提示词")
            else:
                prompt_result = await self.generate_prompt(external_urls=external_urls)
                user_prompt = prompt_result["prompt"]
                logger.info(f"生成提示词成功，时间信息: {prompt_result['time_info']}")

            # 2. 获取系统提示词
            prompts = await self.config_service.get_agent_prompts()
            system_prompt = prompts.get("system_prompt", "")

            # 3. 调用 AI API 接口
            ai_response = await self._call_ai_api(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                ai_models=ai_models
            )
            logger.info("AI API 调用完成")

            # 4. 解析 AI 返回结果生成推荐
            recommendations = await self._parse_ai_response(
                ai_response=ai_response,
                ai_models=ai_models,
                batch_id=batch_id
            )
            logger.info(f"解析完成，生成 {len(recommendations)} 个推荐")

            # 创建批次
            batch = FuturesRecommendationBatch(
                batch_id=batch_id,
                cycle_time=now_tz(),
                total_recommendations=len(recommendations),
                successful_recommendations=len(recommendations),
                failed_recommendations=0,
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
                failed_recommendations=0,
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

    async def _call_ai_api(
        self,
        system_prompt: str,
        user_prompt: str,
        ai_models: List[str]
    ) -> Dict[str, Any]:
        """
        调用 AI API 接口

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词（由 generate_prompt 生成）
            ai_models: AI 模型列表

        Returns:
            AI 响应结果字典，包含模型名称和响应内容
        """
        results = {}

        for model in ai_models:
            try:
                response = await self._call_single_ai_model(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model
                )
                if response:
                    results[model] = response
                    # 只需要一个模型成功响应即可
                    break
            except Exception as e:
                logger.error(f"AI模型 {model} 调用失败: {e}")
                continue

        return {
            "model_used": list(results.keys())[0] if results else None,
            "response": list(results.values())[0] if results else None,
            "all_responses": results
        }

    async def _parse_ai_response(
        self,
        ai_response: Dict[str, Any],
        ai_models: List[str],
        batch_id: str
    ) -> List[FuturesRecommendation]:
        """
        解析 AI 返回结果生成推荐列表

        Args:
            ai_response: AI API 返回的响应
            ai_models: 使用的 AI 模型列表
            batch_id: 批次 ID

        Returns:
            推荐列表
        """
        recommendations = []
        response_text = ai_response.get("response", "")

        if not response_text:
            logger.warning("AI 响应为空，无法生成推荐")
            return recommendations

        # 解析 AI 响应中的推荐信息
        # AI 返回的是包含5个期货品种推荐的完整分析报告
        # 这里创建一个汇总推荐记录
        try:
            recommendation = FuturesRecommendation(
                recommendation_id=f"rec_{batch_id}_{uuid.uuid4().hex[:8]}",
                batch_id=batch_id,
                futures_symbol="SUMMARY",  # 汇总推荐
                futures_name="期货推荐汇总",
                direction=FuturesDirection.LONG,  # 默认值
                entry_range=EntryRange(min_price=0, max_price=0),
                take_profit=0,
                stop_loss=0,
                holding_time="见详细分析",
                confidence_score=0.8,
                ai_models_used=ai_models,
                analysis_reports=AnalysisReport(
                    technical_analysis=response_text,
                    summary=response_text[:1000] if len(response_text) > 1000 else response_text
                ),
                status=RecommendationStatus.ACTIVE
            )

            # 保存到数据库
            await self._save_recommendation(recommendation)
            recommendations.append(recommendation)

        except Exception as e:
            logger.error(f"创建推荐记录失败: {e}")

        return recommendations

    async def _call_ai_models(
        self,
        system_prompt: str,
        user_prompt: str,
        ai_models: List[str]
    ) -> Dict[str, str]:
        """并行调用多个AI模型（保留兼容）"""
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

    async def generate_prompt(
        self,
        external_urls: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        生成期货提示词

        功能：
        1. 获取提示词模板
        2. 从外部HTTPS请求获取JSON数据（第一个URL为宏观经济数据，第二个URL为期货品种价格数据）
        3. 获取当前北京时间和开仓时间（当前时间+10分钟）
        4. 将数据填充到模板中生成完整提示词

        Args:
            external_urls: 外部数据URL列表，不传则使用配置中的URL

        Returns:
            包含提示词和时间信息的字典
        """
        # 获取外部数据URL（优先使用请求参数，否则使用配置，最后使用默认值）
        urls_to_fetch = external_urls
        if not urls_to_fetch:
            config = await self.config_service.get_active_config()
            if config and config.external_data_urls:
                urls_to_fetch = config.external_data_urls
            else:
                urls_to_fetch = DEFAULT_EXTERNAL_URLS
                logger.info("使用默认外部数据URL")

        # 从外部URL获取JSON数据
        external_data_list = await self._fetch_external_data(urls_to_fetch)

        # 获取当前北京时间
        beijing_tz = pytz.timezone("Asia/Shanghai")
        current_time = datetime.now(beijing_tz)
        # 开仓时间为当前时间+10分钟
        entry_time = current_time + timedelta(minutes=10)

        # 格式化时间
        current_time_str = current_time.strftime("%Y年%m月%d日%H:%M:%S")
        entry_time_str = entry_time.strftime("%H:%M")
        table_time_format = current_time.strftime("%Y年%m月%d日%H:%M:%S")

        # 提取宏观经济数据和期货品种价格数据
        macro_economic_data = ""
        futures_price_data = ""

        if len(external_data_list) >= 1 and "data" in external_data_list[0]:
            macro_economic_data = json.dumps(external_data_list[0]["data"], ensure_ascii=False, indent=2)

        if len(external_data_list) >= 2 and "data" in external_data_list[1]:
            futures_price_data = json.dumps(external_data_list[1]["data"], ensure_ascii=False, indent=2)

        # 使用模板生成完整提示词
        full_prompt = FUTURES_PROMPT_TEMPLATE.format(
            table_time_format=table_time_format,
            macro_economic_data=macro_economic_data,
            futures_price_data=futures_price_data,
            current_time=current_time_str,
            entry_time=entry_time_str
        )

        return {
            "prompt": full_prompt,
            "time_info": {
                "current_time": current_time_str,
                "entry_time": entry_time_str,
                "timezone": "Asia/Shanghai"
            }
        }

    async def _fetch_external_data(
        self,
        urls: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """
        从外部URL获取JSON数据

        Args:
            urls: URL列表

        Returns:
            包含URL和数据/错误信息的列表
        """
        external_data_list = []
        if not urls:
            return external_data_list

        async with httpx.AsyncClient(timeout=30.0) as client:
            for url in urls:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                    external_data_list.append({
                        "url": url,
                        "data": data
                    })
                    logger.info(f"成功获取外部数据: {url}")
                except httpx.HTTPStatusError as e:
                    logger.warning(f"获取外部数据失败 ({url}): HTTP {e.response.status_code}")
                    external_data_list.append({
                        "url": url,
                        "error": f"HTTP {e.response.status_code}"
                    })
                except httpx.RequestError as e:
                    logger.warning(f"获取外部数据失败 ({url}): {str(e)}")
                    external_data_list.append({
                        "url": url,
                        "error": str(e)
                    })
                except json.JSONDecodeError:
                    logger.warning(f"解析JSON失败 ({url})")
                    external_data_list.append({
                        "url": url,
                        "error": "JSON解析失败"
                    })

        return external_data_list


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
