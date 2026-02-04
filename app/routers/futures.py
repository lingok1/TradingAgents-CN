"""
期货推荐API路由
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.routers.auth_db import get_current_user
from app.models.futures import (
    GenerateRecommendationRequest, RecommendationResponse,
    FuturesRecommendation, FuturesRecommendationBatch
)
from app.services.futures_recommendation_service import get_futures_recommendation_service
from app.services.futures_scheduler_service import get_futures_scheduler_service
from app.services.futures_config_service import get_futures_config_service

router = APIRouter(prefix="/api/futures", tags=["futures"])
logger = logging.getLogger("futures_api")


# 请求/响应模型
class UpdatePromptsRequest(BaseModel):
    """更新提示词请求"""
    system_prompt: str = Field(..., description="系统提示词")
    user_prompt_template: str = Field(..., description="用户提示词模板")


class UpdateSymbolsRequest(BaseModel):
    """更新品种列表请求"""
    symbols: List[str] = Field(..., description="期货品种代码列表")


class UpdateAIModelsRequest(BaseModel):
    """更新AI模型请求"""
    ai_models: List[Dict[str, Any]] = Field(..., description="AI模型配置列表")


class UpdateExternalUrlsRequest(BaseModel):
    """更新外部数据URL请求"""
    urls: List[str] = Field(..., description="外部数据URL列表")


# ==================== 推荐相关接口 ====================

@router.post("/recommendations/generate", response_model=Dict[str, Any])
async def generate_recommendations(
    request: GenerateRecommendationRequest,
    user: dict = Depends(get_current_user)
):
    """
    手动触发推荐生成

    流程：
    1. 调用 generate_prompt 获取完整提示词（包含宏观经济和期货价格数据）
    2. 将提示词发送给 AI API 接口
    3. 解析 AI 返回结果生成推荐
    """
    try:
        logger.info(f"用户 {user['id']} 请求生成推荐")
        logger.info(f"请求参数: {request}")

        service = get_futures_recommendation_service()
        batch = await service.generate_recommendations(
            symbols=request.symbols,
            ai_models=request.ai_models,
            custom_prompt=request.custom_prompt,
            external_urls=request.external_urls
        )

        return {
            "success": True,
            "data": {
                "batch_id": batch.batch_id,
                "total_recommendations": batch.total_recommendations,
                "successful_recommendations": batch.successful_recommendations,
                "failed_recommendations": batch.failed_recommendations,
                "execution_time_ms": batch.execution_time_ms,
                "recommendations": [
                    rec.model_dump(by_alias=True) for rec in batch.recommendations
                ]
            },
            "message": "推荐生成成功"
        }
    except Exception as e:
        logger.error(f"生成推荐失败: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/recommendations/latest", response_model=Dict[str, Any])
async def get_latest_recommendations(
    limit: int = Query(5, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    user: dict = Depends(get_current_user)
):
    """获取最新推荐"""
    try:
        logger.info(f"用户 {user['id']} 请求获取最新推荐")

        service = get_futures_recommendation_service()
        batches = await service.get_latest_recommendations(limit=limit, offset=offset)

        return {
            "success": True,
            "data": {
                "total": len(batches),
                "batches": [
                    {
                        "batch_id": batch.batch_id,
                        "cycle_time": batch.cycle_time.isoformat(),
                        "total_recommendations": batch.total_recommendations,
                        "successful_recommendations": batch.successful_recommendations,
                        "failed_recommendations": batch.failed_recommendations,
                        "execution_time_ms": batch.execution_time_ms,
                        "created_at": batch.created_at.isoformat()
                    }
                    for batch in batches
                ]
            },
            "message": "获取成功"
        }
    except Exception as e:
        logger.error(f"获取最新推荐失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/recommendations/{batch_id}", response_model=Dict[str, Any])
async def get_batch_recommendations(
    batch_id: str,
    user: dict = Depends(get_current_user)
):
    """获取特定批次的推荐"""
    try:
        logger.info(f"用户 {user['id']} 请求获取批次 {batch_id} 的推荐")

        service = get_futures_recommendation_service()
        batch = await service.get_batch_by_id(batch_id)

        if not batch:
            raise HTTPException(status_code=404, detail="批次不存在")

        return {
            "success": True,
            "data": {
                "batch_id": batch.batch_id,
                "cycle_time": batch.cycle_time.isoformat(),
                "total_recommendations": batch.total_recommendations,
                "successful_recommendations": batch.successful_recommendations,
                "failed_recommendations": batch.failed_recommendations,
                "execution_time_ms": batch.execution_time_ms,
                "ai_models_used": batch.ai_models_used,
                "recommendations": [
                    {
                        "recommendation_id": rec.recommendation_id,
                        "futures_symbol": rec.futures_symbol,
                        "futures_name": rec.futures_name,
                        "direction": rec.direction.value,
                        "entry_range": {
                            "min_price": rec.entry_range.min_price,
                            "max_price": rec.entry_range.max_price
                        },
                        "take_profit": rec.take_profit,
                        "stop_loss": rec.stop_loss,
                        "holding_time": rec.holding_time,
                        "confidence_score": rec.confidence_score,
                        "ai_models_used": rec.ai_models_used,
                        "analysis_reports": rec.analysis_reports.model_dump(),
                        "status": rec.status.value,
                        "created_at": rec.created_at.isoformat()
                    }
                    for rec in batch.recommendations
                ],
                "created_at": batch.created_at.isoformat()
            },
            "message": "获取成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取批次推荐失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/recommendations/history/{symbol}", response_model=Dict[str, Any])
async def get_recommendation_history(
    symbol: str,
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    user: dict = Depends(get_current_user)
):
    """获取品种推荐历史"""
    try:
        logger.info(f"用户 {user['id']} 请求获取 {symbol} 的推荐历史")

        # 解析日期
        start_dt = None
        end_dt = None
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
        if end_date:
            end_dt = datetime.fromisoformat(end_date)

        service = get_futures_recommendation_service()
        recommendations = await service.get_recommendation_history(
            symbol=symbol,
            start_date=start_dt,
            end_date=end_dt,
            limit=limit
        )

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "total": len(recommendations),
                "recommendations": [
                    {
                        "recommendation_id": rec.recommendation_id,
                        "batch_id": rec.batch_id,
                        "direction": rec.direction.value,
                        "entry_range": {
                            "min_price": rec.entry_range.min_price,
                            "max_price": rec.entry_range.max_price
                        },
                        "take_profit": rec.take_profit,
                        "stop_loss": rec.stop_loss,
                        "holding_time": rec.holding_time,
                        "confidence_score": rec.confidence_score,
                        "status": rec.status.value,
                        "created_at": rec.created_at.isoformat()
                    }
                    for rec in recommendations
                ]
            },
            "message": "获取成功"
        }
    except Exception as e:
        logger.error(f"获取推荐历史失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 定时任务相关接口 ====================

@router.get("/scheduler/status", response_model=Dict[str, Any])
async def get_scheduler_status(
    user: dict = Depends(get_current_user)
):
    """获取定时任务状态"""
    try:
        logger.info(f"用户 {user['id']} 请求获取定时任务状态")

        scheduler_service = get_futures_scheduler_service()
        stats = await scheduler_service.get_execution_stats("futures_recommendation_scheduler")
        is_trading_time = scheduler_service.is_trading_time()

        return {
            "success": True,
            "data": {
                "job_id": "futures_recommendation_scheduler",
                "job_name": "期货推荐定时任务",
                "is_trading_time": is_trading_time,
                "execution_stats": stats
            },
            "message": "获取成功"
        }
    except Exception as e:
        logger.error(f"获取定时任务状态失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/scheduler/trigger", response_model=Dict[str, Any])
async def trigger_scheduler(
    user: dict = Depends(get_current_user)
):
    """手动触发定时任务"""
    try:
        logger.info(f"用户 {user['id']} 请求手动触发定时任务")

        scheduler_service = get_futures_scheduler_service()
        batch_id = await scheduler_service.execute_recommendation_task()

        if batch_id:
            return {
                "success": True,
                "data": {"batch_id": batch_id},
                "message": "任务执行成功"
            }
        else:
            return {
                "success": False,
                "data": None,
                "message": "任务执行失败或不在交易时间"
            }
    except Exception as e:
        logger.error(f"手动触发定时任务失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/scheduler/history", response_model=Dict[str, Any])
async def get_scheduler_history(
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    user: dict = Depends(get_current_user)
):
    """获取定时任务执行历史"""
    try:
        logger.info(f"用户 {user['id']} 请求获取定时任务执行历史")

        scheduler_service = get_futures_scheduler_service()
        records = await scheduler_service.get_execution_history(
            job_id="futures_recommendation_scheduler",
            limit=limit,
            offset=offset
        )

        return {
            "success": True,
            "data": {
                "total": len(records),
                "records": [
                    {
                        "job_id": rec.job_id,
                        "job_name": rec.job_name,
                        "batch_id": rec.batch_id,
                        "status": rec.status,
                        "scheduled_time": rec.scheduled_time.isoformat(),
                        "execution_time": rec.execution_time.isoformat(),
                        "duration_ms": rec.duration_ms,
                        "total_recommendations": rec.total_recommendations,
                        "successful_count": rec.successful_count,
                        "failed_count": rec.failed_count,
                        "error_message": rec.error_message,
                        "created_at": rec.created_at.isoformat()
                    }
                    for rec in records
                ]
            },
            "message": "获取成功"
        }
    except Exception as e:
        logger.error(f"获取定时任务执行历史失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 配置相关接口 ====================

@router.get("/config", response_model=Dict[str, Any])
async def get_config(
    user: dict = Depends(get_current_user)
):
    """获取推荐系统配置"""
    try:
        logger.info(f"用户 {user['id']} 请求获取配置")

        config_service = get_futures_config_service()
        config = await config_service.get_active_config()

        if not config:
            config = await config_service.get_or_create_default_config()

        return {
            "success": True,
            "data": {
                "trading_hours": config.trading_hours,
                "futures_symbols": config.futures_symbols,
                "recommendation_interval_minutes": config.recommendation_interval_minutes,
                "ai_models": [
                    {
                        "provider": model.get("provider"),
                        "model": model.get("model"),
                        "enabled": model.get("enabled", True),
                        "priority": model.get("priority", 999)
                    }
                    for model in config.ai_models
                ],
                "agent_prompts": {
                    "system_prompt": config.agent_prompts.get("system_prompt", "")[:200] + "...",
                    "user_prompt_template": config.agent_prompts.get("user_prompt_template", "")[:200] + "..."
                }
            },
            "message": "获取成功"
        }
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/config/prompts", response_model=Dict[str, Any])
async def update_prompts(
    request: UpdatePromptsRequest,
    user: dict = Depends(get_current_user)
):
    """更新Agent提示词"""
    try:
        logger.info(f"用户 {user['id']} 请求更新提示词")

        config_service = get_futures_config_service()
        success = await config_service.update_agent_prompts({
            "system_prompt": request.system_prompt,
            "user_prompt_template": request.user_prompt_template
        })

        if success:
            return {
                "success": True,
                "message": "提示词更新成功"
            }
        else:
            raise HTTPException(status_code=400, detail="提示词更新失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新提示词失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/config/symbols", response_model=Dict[str, Any])
async def update_symbols(
    request: UpdateSymbolsRequest,
    user: dict = Depends(get_current_user)
):
    """更新期货品种列表"""
    try:
        logger.info(f"用户 {user['id']} 请求更新品种列表")

        config_service = get_futures_config_service()
        success = await config_service.update_futures_symbols(request.symbols)

        if success:
            return {
                "success": True,
                "data": {"symbols": request.symbols},
                "message": "品种列表更新成功"
            }
        else:
            raise HTTPException(status_code=400, detail="品种列表更新失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新品种列表失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/config/ai-models", response_model=Dict[str, Any])
async def update_ai_models(
    request: UpdateAIModelsRequest,
    user: dict = Depends(get_current_user)
):
    """更新AI模型配置"""
    try:
        logger.info(f"用户 {user['id']} 请求更新AI模型配置")

        config_service = get_futures_config_service()
        success = await config_service.update_ai_models(request.ai_models)

        if success:
            return {
                "success": True,
                "data": {"ai_models": request.ai_models},
                "message": "AI模型配置更新成功"
            }
        else:
            raise HTTPException(status_code=400, detail="AI模型配置更新失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新AI模型配置失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/config/external-urls", response_model=Dict[str, Any])
async def update_external_urls(
    request: UpdateExternalUrlsRequest,
    user: dict = Depends(get_current_user)
):
    """更新外部数据URL配置"""
    try:
        logger.info(f"用户 {user['id']} 请求更新外部数据URL配置")

        config_service = get_futures_config_service()
        success = await config_service.update_external_data_urls(request.urls)

        if success:
            return {
                "success": True,
                "data": {"urls": request.urls},
                "message": "外部数据URL配置更新成功"
            }
        else:
            raise HTTPException(status_code=400, detail="外部数据URL配置更新失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新外部数据URL配置失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/config/external-urls", response_model=Dict[str, Any])
async def get_external_urls(
    user: dict = Depends(get_current_user)
):
    """获取外部数据URL配置"""
    try:
        logger.info(f"用户 {user['id']} 请求获取外部数据URL配置")

        config_service = get_futures_config_service()
        urls = await config_service.get_external_data_urls()

        return {
            "success": True,
            "data": {"urls": urls},
            "message": "获取成功"
        }
    except Exception as e:
        logger.error(f"获取外部数据URL配置失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ==================== 健康检查 ====================

@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """期货推荐系统健康检查"""
    return {
        "success": True,
        "status": "healthy",
        "message": "期货推荐系统正常运行"
    }


# ==================== 提示词生成接口 ====================

@router.get("/prompt/generate", response_model=Dict[str, Any])
async def generate_prompt(
    external_urls: Optional[List[str]] = Query(None, description="外部数据URL列表，不传则使用配置中的URL。第一个URL为宏观经济数据，第二个URL为期货品种价格数据"),
    user: dict = Depends(get_current_user)
):
    """
    获取期货提示词生成接口

    功能：
    1. 获取提示词模板
    2. 从外部HTTPS请求获取JSON数据（第一个URL为宏观经济数据，第二个URL为期货品种价格数据）
    3. 获取当前北京时间和开仓时间（当前时间+10分钟）
    4. 将数据填充到模板中生成完整提示词
    """
    try:
        logger.info(f"用户 {user['id']} 请求生成提示词")

        service = get_futures_recommendation_service()
        result = await service.generate_prompt(external_urls=external_urls)

        return {
            "success": True,
            "data": result,
            "message": "提示词生成成功"
        }
    except Exception as e:
        logger.error(f"生成提示词失败: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
