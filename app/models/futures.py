"""
期货相关数据模型
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from bson import ObjectId
from .user import PyObjectId
from app.utils.timezone import now_tz


class FuturesDirection(str, Enum):
    """期货方向枚举"""
    LONG = "多"
    SHORT = "空"


class RecommendationStatus(str, Enum):
    """推荐状态枚举"""
    ACTIVE = "active"  # 活跃推荐
    EXPIRED = "expired"  # 已过期
    CLOSED = "closed"  # 已平仓
    CANCELLED = "cancelled"  # 已取消


class FuturesData(BaseModel):
    """期货实时数据模型"""
    symbol: str = Field(..., description="期货代码，如IF2412")
    name: str = Field(..., description="期货名称")
    price: float = Field(..., description="当前价格")
    bid: float = Field(..., description="买价")
    ask: float = Field(..., description="卖价")
    volume: int = Field(..., description="成交量")
    open_interest: int = Field(..., description="持仓量")
    timestamp: datetime = Field(default_factory=now_tz, description="数据时间戳")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "symbol": "IF2412",
            "name": "沪深300指数期货",
            "price": 3500.5,
            "bid": 3500.4,
            "ask": 3500.6,
            "volume": 1000000,
            "open_interest": 500000,
            "timestamp": "2024-01-26T10:30:00+08:00"
        }
    })


class EntryRange(BaseModel):
    """入场区间模型"""
    min_price: float = Field(..., description="最低入场价")
    max_price: float = Field(..., description="最高入场价")


class AnalysisReport(BaseModel):
    """分析报告模型"""
    technical_analysis: Optional[str] = Field(None, description="技术面分析")
    fundamental_analysis: Optional[str] = Field(None, description="基本面分析")
    capital_flow_analysis: Optional[str] = Field(None, description="资金面分析")
    bull_debate: Optional[str] = Field(None, description="多头博弈")
    bear_debate: Optional[str] = Field(None, description="空头博弈")
    summary: Optional[str] = Field(None, description="综合分析总结")


class FuturesRecommendation(BaseModel):
    """期货推荐模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    recommendation_id: str = Field(..., description="推荐唯一标识")
    batch_id: str = Field(..., description="批次ID")
    user_id: Optional[PyObjectId] = Field(None, description="用户ID")

    # 期货信息
    futures_symbol: str = Field(..., description="期货代码，如IF2412")
    futures_name: str = Field(..., description="期货名称")

    # 推荐信息
    direction: FuturesDirection = Field(..., description="推荐方向：多/空")
    entry_range: EntryRange = Field(..., description="入场区间")
    take_profit: float = Field(..., description="止盈价")
    stop_loss: float = Field(..., description="止损价")
    holding_time: str = Field(..., description="建议持仓时间，如'1小时'、'4小时'")

    # 分析信息
    confidence_score: float = Field(..., ge=0, le=1, description="推荐置信度 0-1")
    ai_models_used: List[str] = Field(default_factory=list, description="使用的AI模型列表")
    analysis_reports: AnalysisReport = Field(default_factory=AnalysisReport, description="各维度分析报告")

    # 状态信息
    status: RecommendationStatus = Field(default=RecommendationStatus.ACTIVE, description="推荐状态")
    created_at: datetime = Field(default_factory=now_tz, description="创建时间")
    updated_at: datetime = Field(default_factory=now_tz, description="更新时间")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recommendation_id": "rec_20240126_001",
                "batch_id": "batch_20240126_093000",
                "futures_symbol": "IF2412",
                "futures_name": "沪深300指数期货",
                "direction": "多",
                "entry_range": {"min_price": 3500.0, "max_price": 3510.0},
                "take_profit": 3530.0,
                "stop_loss": 3490.0,
                "holding_time": "4小时",
                "confidence_score": 0.85,
                "ai_models_used": ["gpt-4", "deepseek-chat"],
                "status": "active"
            }
        },
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


class FuturesRecommendationBatch(BaseModel):
    """期货推荐批次模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    batch_id: str = Field(..., description="批次唯一标识")
    user_id: Optional[PyObjectId] = Field(None, description="用户ID")

    # 批次信息
    cycle_time: datetime = Field(..., description="推荐周期时间")
    total_recommendations: int = Field(..., description="推荐总数")
    successful_recommendations: int = Field(default=0, description="成功推荐数")
    failed_recommendations: int = Field(default=0, description="失败推荐数")

    # 推荐列表
    recommendations: List[FuturesRecommendation] = Field(default_factory=list, description="推荐列表")

    # 执行信息
    execution_time_ms: float = Field(default=0, description="执行耗时（毫秒）")
    ai_models_used: List[str] = Field(default_factory=list, description="本批次使用的AI模型")

    # 时间戳
    created_at: datetime = Field(default_factory=now_tz, description="创建时间")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "batch_id": "batch_20240126_093000",
                "cycle_time": "2024-01-26T09:30:00+08:00",
                "total_recommendations": 5,
                "successful_recommendations": 5,
                "failed_recommendations": 0,
                "execution_time_ms": 2500.5,
                "ai_models_used": ["gpt-4", "deepseek-chat"]
            }
        },
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


class GenerateRecommendationRequest(BaseModel):
    """生成推荐请求模型"""
    symbols: Optional[List[str]] = Field(None, description="期货代码列表，如['IF', 'IC', 'IH']（已弃用，推荐由AI自动选择）")
    ai_models: Optional[List[str]] = Field(None, description="指定使用的AI模型，不指定则使用配置中的所有启用模型")
    custom_prompt: Optional[str] = Field(None, description="自定义提示词，不指定则使用 generate_prompt 生成")
    external_urls: Optional[List[str]] = Field(None, description="外部数据URL列表，第一个为宏观经济数据，第二个为期货品种价格数据")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "ai_models": ["gpt-4", "deepseek-chat"],
            "custom_prompt": None,
            "external_urls": [
                "https://futsseapi.eastmoney.com/list/custom/CNYOFFS_USDCNH,UDI_UDI,COMEX_GC00Y,NYMEX_CL00Y,EFI_EMFI,CFFEX_IFM,US4_DJIA,SGX_CN00Y,CFFEX_IM2603,SHFE_ag2602,CZCE_UR601,SHFE_fu2601,SHFE_cu2601?orderBy=&sort=&pageSize=999&pageIndex=0&specificContract=true&platform=zbPC&field=name,p,zdf,vol,ccl,rz,tjd,cje,zde,o,h,l,zf,zjsj,zt,dt,dm,sc,tag,uid,zsjd",
                "https://futsseapi.eastmoney.com/list/trans/block/risk/mk0830?orderBy=&sort=&pageSize=999&pageIndex=0&specificContract=true&platform=zbPC&field=name,p,zdf,vol,ccl,rz,tjd,cje,zde,o,h,l,zf,zjsj,zt,dt,dm,sc,tag,uid,zsjd"
            ]
        }
    })


class RecommendationResponse(BaseModel):
    """推荐响应模型"""
    success: bool = Field(..., description="是否成功")
    batch_id: Optional[str] = Field(None, description="批次ID")
    recommendations: Optional[List[FuturesRecommendation]] = Field(None, description="推荐列表")
    message: Optional[str] = Field(None, description="消息")
    error: Optional[str] = Field(None, description="错误信息")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "batch_id": "batch_20240126_093000",
            "recommendations": [],
            "message": "推荐生成成功"
        }
    })


class FuturesConfig(BaseModel):
    """期货配置模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    config_type: str = Field(default="futures_recommendation", description="配置类型")

    # 交易时间配置
    trading_hours: Dict[str, str] = Field(
        default={
            "morning_start": "09:30",
            "morning_end": "11:30",
            "afternoon_start": "13:00",
            "afternoon_end": "15:00",
            "night_start": "21:00",
            "night_end": "23:30"
        },
        description="交易时间配置"
    )

    # 外部数据URL配置（用于提示词生成）
    external_data_urls: List[str] = Field(
        default_factory=list,
        description="外部数据URL列表，用于获取JSON数据追加到提示词"
    )

    # AI模型配置
    ai_models: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="AI模型配置列表"
    )

    # 期货品种列表
    futures_symbols: List[str] = Field(
        default=["IF", "IC", "IH", "T", "TF"],
        description="期货品种代码列表"
    )

    # Agent提示词配置
    agent_prompts: Dict[str, str] = Field(
        default_factory=dict,
        description="Agent提示词配置"
    )

    # 推荐周期配置
    recommendation_interval_minutes: int = Field(
        default=10,
        description="推荐生成间隔（分钟）"
    )

    # 时间戳
    created_at: datetime = Field(default_factory=now_tz, description="创建时间")
    updated_at: datetime = Field(default_factory=now_tz, description="更新时间")
    is_active: bool = Field(default=True, description="是否激活")

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class SchedulerExecutionRecord(BaseModel):
    """定时任务执行记录模型"""
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    job_id: str = Field(..., description="任务ID")
    job_name: str = Field(..., description="任务名称")
    batch_id: Optional[str] = Field(None, description="关联的批次ID")

    # 执行信息
    status: str = Field(..., description="执行状态：success/failed/timeout")
    scheduled_time: datetime = Field(..., description="计划执行时间")
    execution_time: datetime = Field(..., description="实际执行时间")
    duration_ms: float = Field(..., description="执行耗时（毫秒）")

    # 结果信息
    total_recommendations: int = Field(default=0, description="生成的推荐总数")
    successful_count: int = Field(default=0, description="成功推荐数")
    failed_count: int = Field(default=0, description="失败推荐数")

    # 错误信息
    error_message: Optional[str] = Field(None, description="错误信息")
    error_traceback: Optional[str] = Field(None, description="错误堆栈跟踪")

    # 时间戳
    created_at: datetime = Field(default_factory=now_tz, description="记录创建时间")

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
