# 期货推荐系统实现文档

## 概述

业务需求1的实现：在周一到周五白天日间上下午和夜盘交易时间，10分钟循环调用国内外多家AI的API，agent自定义提示词，期货品种响应为JSON数据和前端表格展示。

## 系统架构

### 核心组件

1. **数据模型层** (`app/models/futures.py`)
   - `FuturesRecommendation`: 单个期货推荐
   - `FuturesRecommendationBatch`: 推荐批次
   - `FuturesConfig`: 系统配置
   - `SchedulerExecutionRecord`: 定时任务执行记录

2. **配置服务** (`app/services/futures_config_service.py`)
   - 管理期货推荐系统的配置
   - 支持动态更新AI模型、品种列表、提示词等

3. **数据源适配器** (`tradingagents/dataflows/providers/futures/`)
   - `TushareFuturesAdapter`: Tushare期货数据适配器
   - `AKShareFuturesAdapter`: AKShare期货数据适配器
   - `FuturesDataManager`: 数据源管理器，支持自动降级

4. **推荐服务** (`app/services/futures_recommendation_service.py`)
   - 生成期货推荐
   - 并行调用多个AI模型
   - 解析和聚合分析结果
   - 数据持久化

5. **定时任务服务** (`app/services/futures_scheduler_service.py`)
   - 执行推荐任务
   - 判断交易时间
   - 记录执行历史

6. **API接口** (`app/routers/futures.py`)
   - 推荐相关接口
   - 定时任务管理接口
   - 配置管理接口

## API接口

### 推荐相关

#### 生成推荐
```
POST /api/futures/recommendations/generate
请求体：
{
  "symbols": ["IF", "IC", "IH"],
  "ai_models": ["gpt-4", "deepseek-chat"],
  "custom_prompt": "自定义提示词（可选）"
}

响应：
{
  "success": true,
  "data": {
    "batch_id": "batch_20240126_093000_abc123",
    "total_recommendations": 3,
    "successful_recommendations": 3,
    "failed_recommendations": 0,
    "execution_time_ms": 2500.5,
    "recommendations": [...]
  },
  "message": "推荐生成成功"
}
```

#### 获取最新推荐
```
GET /api/futures/recommendations/latest?limit=5&offset=0

响应：
{
  "success": true,
  "data": {
    "total": 5,
    "batches": [...]
  },
  "message": "获取成功"
}
```

#### 获取特定批次推荐
```
GET /api/futures/recommendations/{batch_id}

响应：
{
  "success": true,
  "data": {
    "batch_id": "...",
    "recommendations": [...]
  },
  "message": "获取成功"
}
```

#### 获取品种推荐历史
```
GET /api/futures/recommendations/history/{symbol}?start_date=2024-01-01&end_date=2024-01-31&limit=100

响应：
{
  "success": true,
  "data": {
    "symbol": "IF",
    "total": 50,
    "recommendations": [...]
  },
  "message": "获取成功"
}
```

### 定时任务相关

#### 获取定时任务状态
```
GET /api/futures/scheduler/status

响应：
{
  "success": true,
  "data": {
    "job_id": "futures_recommendation_scheduler",
    "job_name": "期货推荐定时任务",
    "is_trading_time": true,
    "execution_stats": {
      "total_executions": 100,
      "successful_executions": 98,
      "failed_executions": 2,
      "success_rate": 0.98,
      "average_duration_ms": 2500.5,
      "total_recommendations": 500
    }
  },
  "message": "获取成功"
}
```

#### 手动触发定时任务
```
POST /api/futures/scheduler/trigger

响应：
{
  "success": true,
  "data": {
    "batch_id": "batch_20240126_093000_abc123"
  },
  "message": "任务执行成功"
}
```

#### 获取定时任务执行历史
```
GET /api/futures/scheduler/history?limit=100&offset=0

响应：
{
  "success": true,
  "data": {
    "total": 100,
    "records": [...]
  },
  "message": "获取成功"
}
```

### 配置相关

#### 获取配置
```
GET /api/futures/config

响应：
{
  "success": true,
  "data": {
    "trading_hours": {...},
    "futures_symbols": ["IF", "IC", "IH", "T", "TF"],
    "recommendation_interval_minutes": 10,
    "ai_models": [...]
  },
  "message": "获取成功"
}
```

#### 更新提示词
```
POST /api/futures/config/prompts
请求体：
{
  "system_prompt": "您是一位专业的期货分析师...",
  "user_prompt_template": "请分析期货品种 {symbol}..."
}

响应：
{
  "success": true,
  "message": "提示词更新成功"
}
```

#### 更新品种列表
```
POST /api/futures/config/symbols
请求体：
{
  "symbols": ["IF", "IC", "IH", "T", "TF", "CU", "AL"]
}

响应：
{
  "success": true,
  "data": {
    "symbols": [...]
  },
  "message": "品种列表更新成功"
}
```

#### 更新AI模型配置
```
POST /api/futures/config/ai-models
请求体：
{
  "ai_models": [
    {
      "provider": "openai",
      "model": "gpt-4",
      "enabled": true,
      "priority": 1
    },
    {
      "provider": "deepseek",
      "model": "deepseek-chat",
      "enabled": true,
      "priority": 2
    }
  ]
}

响应：
{
  "success": true,
  "data": {
    "ai_models": [...]
  },
  "message": "AI模型配置更新成功"
}
```

## 定时任务配置

系统自动配置了三个定时任务：

1. **日间上午** (09:30-11:30)
   - 工作日每10分钟执行一次
   - Job ID: `futures_recommendation_morning`

2. **日间下午** (13:00-15:00)
   - 工作日每10分钟执行一次
   - Job ID: `futures_recommendation_afternoon`

3. **夜盘** (21:00-23:30)
   - 工作日每10分钟执行一次
   - Job ID: `futures_recommendation_night`

## 数据库集合

系统使用以下MongoDB集合：

1. `futures_recommendations` - 单个推荐记录
2. `futures_recommendation_batches` - 推荐批次
3. `futures_configs` - 系统配置
4. `futures_scheduler_executions` - 定时任务执行记录

## 健壮性设计

### 错误处理
- 单个AI模型失败不影响整体流程
- 数据源不可用时自动降级
- 网络超时自动重试（最多3次）
- 详细的错误日志记录

### 性能优化
- 并行调用多个AI模型
- 异步处理所有I/O操作
- 数据库查询优化
- 结果缓存机制

### 可靠性保证
- 定时任务执行历史记录
- 失败任务自动重试
- 交易时间自动判断
- 数据一致性检查

## 使用示例

### Python客户端示例

```python
import httpx
import asyncio

async def test_futures_api():
    async with httpx.AsyncClient() as client:
        # 1. 获取配置
        response = await client.get(
            "http://localhost:8000/api/futures/config",
            headers={"Authorization": "Bearer YOUR_TOKEN"}
        )
        print("配置:", response.json())

        # 2. 生成推荐
        response = await client.post(
            "http://localhost:8000/api/futures/recommendations/generate",
            json={
                "symbols": ["IF", "IC", "IH"],
                "ai_models": ["gpt-4", "deepseek-chat"]
            },
            headers={"Authorization": "Bearer YOUR_TOKEN"}
        )
        batch_id = response.json()["data"]["batch_id"]
        print("推荐批次ID:", batch_id)

        # 3. 获取推荐结果
        response = await client.get(
            f"http://localhost:8000/api/futures/recommendations/{batch_id}",
            headers={"Authorization": "Bearer YOUR_TOKEN"}
        )
        print("推荐结果:", response.json())

        # 4. 获取定时任务状态
        response = await client.get(
            "http://localhost:8000/api/futures/scheduler/status",
            headers={"Authorization": "Bearer YOUR_TOKEN"}
        )
        print("定时任务状态:", response.json())

asyncio.run(test_futures_api())
```

### cURL示例

```bash
# 获取配置
curl -X GET "http://localhost:8000/api/futures/config" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 生成推荐
curl -X POST "http://localhost:8000/api/futures/recommendations/generate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["IF", "IC", "IH"],
    "ai_models": ["gpt-4", "deepseek-chat"]
  }'

# 获取定时任务状态
curl -X GET "http://localhost:8000/api/futures/scheduler/status" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 前端集成

前端应该显示以下信息：

### 推荐表格
- 品种名称和代码
- 推荐方向（多/空）
- 入场区间（最低价-最高价）
- 止盈价
- 止损价
- 持仓时间
- 置信度评分

### 分析报告（可折叠）
- 技术面分析
- 基本面分析
- 资金面分析
- 多头博弈
- 空头博弈

### 定时任务监控
- 当前是否在交易时间
- 最后执行时间
- 执行成功率
- 平均执行耗时

## 注意事项

1. **API密钥配置**
   - 确保在.env文件中配置了所有AI模型的API密钥
   - 支持的模型：OpenAI、DeepSeek、DashScope等

2. **期货数据源**
   - 系统支持Tushare和AKShare两个数据源
   - 建议配置Tushare作为主数据源
   - 系统会自动在数据源不可用时降级

3. **交易时间**
   - 系统自动判断当前是否在交易时间
   - 非交易时间的推荐任务会被跳过
   - 可通过配置修改交易时间

4. **性能考虑**
   - 并行调用多个AI模型可能会增加API成本
   - 建议根据实际需求调整AI模型数量
   - 可以通过缓存机制减少重复调用

## 故障排查

### 推荐生成失败
1. 检查AI模型API密钥是否正确配置
2. 检查期货数据源是否可用
3. 查看日志文件了解具体错误信息

### 定时任务未执行
1. 检查当前是否在交易时间
2. 查看定时任务状态API
3. 检查MongoDB连接是否正常

### 数据不一致
1. 检查MongoDB数据库连接
2. 运行数据一致性检查
3. 查看执行历史记录

## 后续改进

1. **增强AI分析**
   - 集成更多AI模型
   - 实现更复杂的结果聚合算法
   - 支持自定义分析规则

2. **性能优化**
   - 实现结果缓存机制
   - 优化数据库查询
   - 支持批量操作

3. **功能扩展**
   - 支持期权Greeks计算
   - 实现风险监控面板
   - 添加回测系统

4. **用户体验**
   - 改进前端展示
   - 添加实时通知
   - 支持自定义告警规则
