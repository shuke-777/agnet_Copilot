# 电商售后 Copilot

这是一个面向电商客服团队的售后工单 Copilot 项目。

## 当前状态

- 规则文件：`AGENTS.md`
- 总规划：`ecommerce_after_sales_copilot_plan.md`
- 当前进度：`docs/STATUS.md`

## 本地启动

使用项目指定环境：

```bash
/opt/anaconda3/envs/rag_910/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
```

启动后访问：

- 健康检查：`http://127.0.0.1:8000/health`
- Swagger：`http://127.0.0.1:8000/docs`

## 本地测试

```bash
/opt/anaconda3/envs/rag_910/bin/python -m pytest -q
```

## M1 手工测试接口

启动服务后，可以先测试示例订单和物流：

```bash
curl -s http://127.0.0.1:8000/api/orders/ORD-1001
curl -s http://127.0.0.1:8000/api/logistics/ORD-1001
```

`ORD-1001` 是物流异常样例，适合测试催物流工单；`ORD-1002` 是物流正常样例，适合后续对比。

## Copilot + 飞书通知测试

默认不配置真实飞书 Webhook，此时异常物流工单会创建成功，飞书通知状态返回 `disabled`，并记录一条 `feishu_notify` step：

```bash
curl -s -X POST http://127.0.0.1:8000/api/copilot/analyze \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"SESSION-FEISHU-001","user_id":"USER-001","user_message":"我的订单 ORD-1001 怎么还没收到？帮我催一下物流。"}'
```

如果需要测试真实飞书群通知，启动服务前配置：

```bash
export FEISHU_WEBHOOK_URL='你的飞书机器人 Webhook 地址'
/opt/anaconda3/envs/rag_910/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
```

接口返回的 `run_id` 可以继续查询执行步骤：

```bash
curl -s http://127.0.0.1:8000/api/runs/{run_id}/steps
```

创建工单：

```bash
curl -s -X POST http://127.0.0.1:8000/api/tickets \
  -H 'Content-Type: application/json' \
  -d '{"ticket_type":"logistics_delay","priority":"high","user_id":"USER-001","order_id":"ORD-1001","summary":"客户反馈订单一直没有收到，需要催物流。","suggested_action":"联系承运商核实卡点，并同步客户预计处理时效。","created_by":"agent"}'
```

## 后续

后续会按里程碑逐步补齐 Agent 埋点、Copilot 分析闭环、飞书和后台页面。
