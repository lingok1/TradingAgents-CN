# 期货推荐系统快速开始指南

## 系统要求

- Python 3.8+
- MongoDB 4.0+
- Redis 5.0+
- 已配置的AI模型API密钥（OpenAI、DeepSeek等）

## 安装步骤

### 1. 依赖安装

```bash
# 安装期货数据源依赖
pip install tushare akshare

# 安装重试库
pip install tenacity
```

### 2. 配置环境变量

在`.env`文件中添加以下配置：

```env
# MongoDB配置
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=tradingagents

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379

# AI模型配置
OPENAI_API_KEY=your_openai_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key

# Tushare配置（可选）
TUSHARE_TOKEN=your_tushare_token

# 时区配置
TIMEZONE=Asia/Shanghai
```

### 3. 启动应用

```bash
# 启动FastAPI应用
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 快速测试

### 1. 获取系统配置

```bash
curl -X GET "http://localhost:8000/api/futures/config" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 2. 手动生成推荐

```bash
curl -X POST "http://localhost:8000/api/futures/recommendations/generate" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["IF", "IC"],
    "ai_models": ["gpt-4"]
  }'
```

### 3. 查看推荐结果

```bash
# 获取最新推荐
curl -X GET "http://localhost:8000/api/futures/recommendations/latest?limit=5" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 获取特定批次
curl -X GET "http://localhost:8000/api/futures/recommendations/{batch_id}" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. 查看定时任务状态

```bash
curl -X GET "http://localhost:8000/api/futures/scheduler/status" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 定时任务说明

系统会自动在以下时间执行推荐任务：

- **工作日 09:30-11:30**：每10分钟执行一次
- **工作日 13:00-15:00**：每10分钟执行一次
- **工作日 21:00-23:30**：每10分钟执行一次

非交易时间的任务会被自动跳过。

## 配置管理

### 更新期货品种列表

```bash
curl -X POST "http://localhost:8000/api/futures/config/symbols" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["IF", "IC", "IH", "T", "TF", "CU", "AL"]
  }'
```

### 更新AI模型配置

```bash
curl -X POST "http://localhost:8000/api/futures/config/ai-models" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

### 更新Agent提示词

```bash
curl -X POST "http://localhost:8000/api/futures/config/prompts" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "system_prompt": "您是一位专业的期货分析师...",
    "user_prompt_template": "请分析期货品种 {symbol}..."
  }'
```

## 监控和调试

### 查看执行历史

```bash
curl -X GET "http://localhost:8000/api/futures/scheduler/history?limit=50" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 查看品种推荐历史

```bash
curl -X GET "http://localhost:8000/api/futures/recommendations/history/IF?limit=100" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 查看日志

```bash
# 查看应用日志
tail -f logs/tradingagents.log

# 查看期货相关日志
grep "futures" logs/tradingagents.log
```

## 常见问题

### Q: 推荐任务没有执行？
A: 检查以下几点：
1. 确认当前是否在交易时间
2. 检查MongoDB和Redis连接
3. 查看应用日志了解具体错误

### Q: AI模型调用失败？
A: 检查以下几点：
1. 确认API密钥是否正确配置
2. 检查网络连接
3. 查看API配额是否充足

### Q: 数据源不可用？
A: 系统会自动降级到备用数据源：
1. 优先使用Tushare
2. 降级到AKShare
3. 最后降级到BaoStock

### Q: 如何修改交易时间？
A: 通过配置API更新交易时间：
```bash
curl -X POST "http://localhost:8000/api/futures/config/trading-hours" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "trading_hours": {
      "morning_start": "09:30",
      "morning_end": "11:30",
      "afternoon_start": "13:00",
      "afternoon_end": "15:00",
      "night_start": "21:00",
      "night_end": "23:30"
    }
  }'
```

## 性能优化建议

1. **减少AI模型数量**
   - 并行调用多个AI模型会增加API成本
   - 建议根据实际需求选择1-2个主要模型

2. **启用缓存**
   - 系统会自动缓存推荐结果
   - 相同品种的推荐会被复用

3. **优化数据库**
   - 为`futures_recommendations`和`futures_recommendation_batches`创建索引
   - 定期清理过期数据

4. **监控资源使用**
   - 监控CPU和内存使用情况
   - 根据需要调整并发数

## 下一步

1. 集成前端展示
2. 实现推荐结果的实时推送
3. 添加更多分析维度
4. 实现回测系统
5. 添加风险监控面板

## 支持

如有问题，请查看：
- 完整文档：`docs/futures/IMPLEMENTATION.md`
- 代码注释：各个源文件中的详细注释
- 日志文件：`logs/tradingagents.log`
