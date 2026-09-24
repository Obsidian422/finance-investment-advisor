# MCP Server 与 Agent 配置说明

> 本文档记录各 MCP Server 端口、工具清单、Agent 绑定关系及关键配置代码位置，便于快速定位与运维。

---

## 一、MCP Server 配置清单

| # | Server 名称 | 源文件 | 端口 | 提供工具 | 启动命令 |
|---|---|---|---|---|---|
| 1 | turn_human_server | `turn_human_server.py` | **8335** | `turn_human_tool` | `python turn_human_server.py` |
| 2 | stock_predict_mcp_server | `stock_predict_mcp_server.py` | **8336** | `predict_future_7data_tool`、`cal_close_price_trend_tool`、`generation_stock_prediction_report_tool` | `python stock_predict_mcp_server.py` |
| 3 | article_check_mcp_server | `article_check_mcp_server.py` | **9330** | `basic_check_tool`、`professional_check_tool`、`produce_check_result_report_tool`、`produce_refine_report_tool` | `python article_check_mcp_server.py` |
| 4 | finance_consult_mcp_server | `finance_consult_mcp_server.py` | **9339** | `invest_policy_consult_tool`、`finance_news_search_consult_tool` | `python finance_consult_mcp_server.py` |

> 所有 Server 均以 **SSE** 传输方式运行：`mcp.run(transport='sse')`，对外暴露 `http://127.0.0.1:<port>/sse`。
>
> 关键代码：`mcp = FastMCP("<name>", host="0.0.0.0", port=<port>)`（各 Server 文件首部）。

---

## 二、Agent 配置清单

| Agent | 模型 | 挂载的 MCP Server | 备注 |
|---|---|---|---|
| Switch Agent | qwen3.7-plus | 无 | 持有 `handoffs=[investment, turn_human, article_check, consult]` |
| Investment Agent | qwen3.7-plus | stock_predict_mcp_server (8336) | `model_settings=ModelSettings(tool_choice="auto")` |
| Article Check Agent | qwen3.7-plus | article_check_mcp_server (9330) | 同上 |
| Consult Agent | qwen3.7-plus | finance_consult_mcp_server (9339) | 同上 |
| Human Agent（turn_human Agent） | qwen3.7-plus | turn_human_server (8335) | 同上 |

> 模型由根目录 `.env` 的 `LLM_PROVIDER` 决定（当前 `qwen3.7-plus`，走通义千问 DashScope）。

---

## 三、关键代码位置

| 配置项 | 文件 | 位置 |
|---|---|---|
| 4 个 MCP Server 连接（MCPServerSse） | `project2_finance_assistant/multi_user_finance_assistant_main_with_session.py` | `MCPManager.initialize()` 约 37~58 行 |
| 关键 Server 校验 critical_servers | 同上 | 约 137 行 |
| 5 个 Agent 定义 | 同上 | `_initialize_agents()` 约 146~248 行 |
| Handoff 互转配置 | 同上 | 约 243~246 行 |
| Session 创建与隔离 | 同上 | `create_session()` 约 250~261 行 |
| 会话状态结构 | 同上 | `global_sessions` 约 28 行 |
| LLM 统一配置 | `project2_finance_assistant/function_handler.py` | 约 23~43 行 |
| RAG 检索参数（Top K=5、阈值 0.5） | `project2_finance_assistant/finance_consult_mcp_server.py` | `invest_policy_consult()` 约 175~188 行 |
| FastAPI 接口 | `project2_finance_assistant/chat_api.py` | `@app.post("/finance_MultiAgent_MultiMCP")` 约 30 行 |

---

## 四、环境与启动

### .env 关键配置（脱敏）
```ini
LLM_PROVIDER=qwen3.7-plus                       # 驱动模型：通义千问
API_KEY=sk-****                                 # 通义千问 DashScope API Key（已配置）
APP_API_KEY=sk-****                             # 百炼联网检索应用 Key（已配置，可选）
APP_ID=****                                     # 百炼应用 ID（已配置，可选）
server_url=127.0.0.1                            # MCP Server 部署地址（本机）
```

### 启动 / 停止
```bash
# 一键启动 4 个 MCP Server（后台），在仓库根目录执行
bash start_servers.sh

# 或手动分步启动
cd project2_finance_assistant && source venv/bin/activate
nohup python turn_human_server.py        > ../logs/turn_human.log 2>&1 &
nohup python stock_predict_mcp_server.py > ../logs/stock_predict.log 2>&1 &
nohup python article_check_mcp_server.py > ../logs/article_check.log 2>&1 &
nohup python finance_consult_mcp_server.py > ../logs/finance_consult.log 2>&1 &

# 停止
bash stop_servers.sh
```

### 端口占用检查
```bash
ss -lntp | grep -E ':(8335|8336|9330|9339)'
```
