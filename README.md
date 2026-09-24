# 金融投资多智能体助理系统

> 基于 MCP（Model Context Protocol）与 OpenAI Agents SDK 构建的多智能体金融助理，覆盖股价预测、金融咨询、文章风险审查与转人工四大业务场景。系统分两个阶段演进：先手写 MCP 客户端验证 Agent–工具调用协议原理，再基于 Agents SDK 重构为多智能体生产形态。

[![Python](https://img.shields.io/badge/python-3.11+-blue)]()
[![MCP](https://img.shields.io/badge/MCP-1.28-purple)]()
[![Agents SDK](https://img.shields.io/badge/OpenAI%20Agents-0.17-orange)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

## 目录

- [业务背景](#业务背景)
- [两阶段演进](#两阶段演进)
- [系统架构](#系统架构)
- [量化结果](#量化结果)
- [项目目录](#项目目录)
- [环境配置](#环境配置)
- [快速开始](#快速开始)
- [API 文档](#api-文档)
- [数据](#数据)
- [使用说明](#使用说明)
- [LLM 服务商切换](#llm-服务商切换)
- [部署](#部署)
- [测试与评测](#测试与评测)
- [FAQ](#faq)
- [License](#license)

## 业务背景

本系统面向个人投资者，提供一站式智能金融助理服务。用户可通过对话完成以下业务：

- **股价查询与预测**：查询近三天收盘价趋势，基于 EMA 指数移动平均预测未来 7 天走势，生成投资建议报告（固定大纲含风险提示）
- **金融问题咨询**：基于本地知识库 RAG 检索 + 联网检索回答金融政策、投资相关问题，未命中显式拒答并降级
- **金融文章风险审查**：对金融文档进行规范性、专业性双维度审查，生成审查报告或直接改写为高质量文章
- **转人工服务**：当用户表达转人工需求时，按业务场景转接相应人工客服

## 两阶段演进

| 阶段 | 目录 | 定位 |
|---|---|---|
| 阶段一 | `project1_stock_counselor/` | **不使用任何 Agent 框架**，手写 `MCPSSEClient` 编排 3 个 MCP Server：自行完成工具聚合、OpenAI tools schema 转换、按工具名路由到对应 Server、并行工具调用（parallel_tool_calls），端到端验证"LLM 决策 → 远程执行 → 结果回填"的工具调用闭环（业务：行情查询 + 情绪安抚 + 转人工） |
| 阶段二 | `project2_finance_assistant/` | 基于 OpenAI Agents SDK 重构为多智能体系统：4 个 MCP Server + 5 个 Agent，新增本地 RAG、多用户会话隔离、FastAPI/Gradio 服务化入口与评测体系 |

两阶段可独立运行，端口互不冲突（阶段一 7335/7336/7337，阶段二 8335/8336/9330/9339）。

## 系统架构

```
用户输入(命令行 / FastAPI / Gradio)
        │
        ▼
   Switch Agent(业务转接调度)
        │  按 handoff_description 决策转交
        ├─→ Investment Agent    → stock_predict_mcp_server  (股价预测/查询/投资报告)
        ├─→ Article Check Agent → article_check_mcp_server  (规范/专业审查/改稿)
        ├─→ Consult Agent       → finance_consult_mcp_server(本地RAG/联网检索)
        └─→ turn_human Agent    → turn_human_server         (转人工)
                    │
              各 Agent 间通过 handoffs 互转
              完成后回 Switch Agent 等待下一轮
```

**关键组件：**
- `Switch Agent`：业务转接调度，根据用户意图分发到下游专业智能体（自身不挂工具，只做路由）
- `Investment Agent`：股价预测/查询/投资报告，挂载 `stock_predict_mcp_server`
- `Article Check Agent`：金融文章风险审查与改写，挂载 `article_check_mcp_server`
- `Consult Agent`：金融问题咨询（本地 RAG + 联网检索），挂载 `finance_consult_mcp_server`
- `turn_human Agent`：转人工服务，挂载 `turn_human_server`

**工程要点：**
- **MCP 长连接治理**：`MCPManager` 单例统一管理 4 条 SSE 连接，`asyncio.Lock` 双检初始化、每轮对话探活、断连自动重连、启动时逐 Server 校验快速失败
- **多轮记忆**：`result.to_input_list()` 全量回填历史（含 tool 消息链），保证 function-call 上下文完整
- **会话隔离**：uuid 会话保存 `messages + current_agent`，handoff 后同步更新，多用户互不串扰
- **RAG 双路兜底**：本地 ChromaDB 命中即答，未命中返回明确话术并降级百炼联网检索

架构与配置的进一步细节见 [`docs/architecture.md`](docs/architecture.md)、[`docs/configuration.md`](docs/configuration.md)。

## 量化结果

以下指标均由仓库内脚本/日志产出，评测脚本**无需 API Key、纯本地可复跑**：

| 指标 | 结果 | 出处 |
|---|---|---|
| EMA 单日预测 MAPE（滚动回测，3 标的 ×358 天） | 0.92% ~ 0.98% | `metrics/ema_backtest_results.json` |
| 7 步外推 MAPE / 方向准确率 | 3.05%~3.26% / 43%~45%（如实记录为模型局限） | 同上 |
| RAG 命中链路端到端延迟 | 13.6s | `docs/run_logs/run_business.txt` |
| 未命中联网兜底链路延迟 | 31.7s | 同上 |
| 多用户会话隔离测试 | 上下文沿用 / 隔离 / 业务切换三类断言全部通过 | `docs/test_results.md` |
| 系统规模（AST 静态统计） | 7 MCP Server、14 工具、9 处 SSE 客户端连接 | `metrics/project_metrics.json` |

复现方式：`python metrics/quantify_static.py`、`python metrics/quantify_ema_backtest.py`。

## 项目目录

```
finance-investment-advisor/
├── README.md
├── LICENSE
├── requirements.txt                  # 顶层依赖清单(参考用)
├── .env.example                      # 环境变量模板
├── start_servers.sh                  # 一键启动脚本(阶段二)
├── stop_servers.sh                   # 一键停止脚本(进程名+端口双重清理)
├── data/                             # 备用股票日线 CSV
│   └── stock_A~D_daily_close.csv
├── project1_stock_counselor/         # 阶段一:手写 MCP Client 编排 3 个 Server
│   ├── requirements.txt
│   ├── function_utils.py             # 工具函数(EMA预测/趋势/话术/转人工)
│   ├── series_predict.py             # 独立时序预测脚本
│   ├── stock_sever.py                # 股价 MCP Server (端口 7336)
│   ├── policy_reply_server.py        # 策略话术 MCP Server (端口 7337)
│   ├── turn_human_server.py          # 转人工 MCP Server (端口 7335)
│   ├── multi_sse_mcp_client.py       # 手写多 SSE MCP Client + LLM 工具调用循环
│   └── stock_data.xlsx               # 上证指数/中国石油/中国银行 收盘价数据
├── project2_finance_assistant/       # 阶段二:多 Agent 多 MCP 主系统
│   ├── requirements.txt
│   ├── function_handler.py           # 公共函数(LLM调用/EMA/统一LLM配置)
│   ├── turn_human_server.py          # 转人工 MCP Server (端口 8335)
│   ├── stock_predict_mcp_server.py   # 股价预测 MCP Server (端口 8336)
│   ├── article_check_mcp_server.py   # 文章审查 MCP Server (端口 9330)
│   ├── finance_consult_mcp_server.py # 金融咨询 MCP Server (端口 9339, 本地RAG+联网)
│   ├── finance_assistant_main.py     # 主程序(命令行多轮交互)
│   ├── multi_user_finance_assistant_main_with_session.py  # 主程序(多用户会话管理)
│   ├── chat_api.py                   # FastAPI 接口服务 (端口 9998)
│   ├── chat_api_post.py              # 接口测试脚本
│   ├── gradio_demo.py                # Gradio 前端 (端口 9996)
│   ├── 投资政策.xlsx                  # RAG 知识库源数据
│   └── 全球增长基金的表现与风险分析.docx  # 文章审查样例文档
├── docs/                             # 架构/配置/运行结果/测试/调试文档
│   ├── architecture.md  configuration.md
│   ├── run_results.md  test_results.md  debug_log.md
│   └── run_logs/                     # 端到端运行与测试的原始日志
├── tests/                            # 自动化测试脚本
│   ├── run_business_demo.py          # 端到端业务回归(含 RAG 相似度探针)
│   └── test_multi_user.py            # 多用户会话隔离测试(三类断言)
└── metrics/                          # 量化评测脚本与结果
    ├── quantify_static.py  quantify_ema_backtest.py
    └── project_metrics.json  ema_backtest_results.json
```

## 环境配置

**系统要求：**
- OS: Ubuntu 20.04+ / CentOS 7+（Windows 需 WSL2）
- Python: 3.11+
- 无需 GPU（纯 CPU 即可运行，模型调用走云端 API）

**技术栈：**

| 层 | 技术 |
|---|---|
| LLM | 通义千问 `qwen-plus`(DashScope) 或 DeepSeek `deepseek-chat`，二选一 |
| Agent 框架 | OpenAI Agents SDK(`openai-agents`) |
| MCP | `mcp` 库：`FastMCP` Server + SSE Client |
| 向量库/Embedding | ChromaDB `1.0.8` + 通义 `text-embedding-v1` |
| 联网检索 | 阿里云百炼 `dashscope.Application`（可选） |
| 时序预测 | `statsmodels`（指数移动平均 EMA） |
| Web 服务 | `FastAPI` + `uvicorn` |
| 前端 | `Gradio` |
| 文档处理 | `python-docx` |

**安装（两个阶段分别使用独立虚拟环境）：**

```bash
# 阶段一环境
cd project1_stock_counselor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 阶段二环境
cd ../project2_finance_assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**配置环境变量：**

```bash
cp .env.example .env
# 同时复制一份到阶段二目录(供 function_handler 等模块加载)
cp .env.example project2_finance_assistant/.env
```

编辑 `.env`，至少配置一个 LLM API Key（详见 [LLM 服务商切换](#llm-服务商切换)）。

## 快速开始

以阶段二为例，3 步跑通一次对话：

```bash
# 1. 进入项目根目录
cd finance-investment-advisor

# 2. 配置 .env(至少填一个 API Key + server_url=127.0.0.1)

# 3. 一键启动 4 个 MCP Server 并选择主程序入口
bash start_servers.sh
# 脚本自动激活虚拟环境，后台启动 4 个 MCP Server(8335/8336/9330/9339)，日志输出到 logs/
# 然后交互式选择主程序入口：①命令行 ②FastAPI ③Gradio ④仅启动 MCP Server
```

> 首次运行还需向向量库灌入知识（仅一次），需先激活虚拟环境后执行：
> ```bash
> cd project2_finance_assistant && source venv/bin/activate
> python -c "from finance_consult_mcp_server import qwen_db, document_list; [qwen_db.add_documents(documents=[e]) for e in document_list]; print('知识库初始化完成')"
> ```

测试输入示例：

```
请输入本轮消息：我想咨询一下近期上证指数的收盘价
请输入本轮消息：顺带预测一下未来的趋势
请输入本轮消息：好的，生成报告吧
请输入本轮消息：没有了，谢谢
```

## API 文档

启动 FastAPI 服务后访问 `http://localhost:9998/docs` 查看 Swagger 文档。核心 endpoint：

### POST `/finance_MultiAgent_MultiMCP`

**请求：**
```json
{
  "current_message": "查询一下中国石油近期收盘价数据",
  "session_id": ""
}
```

**返回：**
```json
{
  "session_id": "462c5f81-2f10-4e3d-9225-3fd3351c6e3c",
  "response": "查询到股票:中国石油,近三天的平均收盘价为:...",
  "status": "success"
}
```

| 字段 | 说明 |
|---|---|
| `current_message` | 本轮用户消息 |
| `session_id` | 会话 ID，首次传空字符串由后端创建；后续传入同一 ID 实现多轮对话 |

接口测试脚本见 `chat_api_post.py`。

## 数据

| 数据文件 | 用途 | 位置 |
|---|---|---|
| `stock_data.xlsx` | 股价查询与预测（上证指数/中国石油/中国银行 三个 sheet，各 378 天日线） | `project1_stock_counselor/` |
| `投资政策.xlsx` | RAG 知识库源数据（50 条投资政策） | `project2_finance_assistant/` |
| `全球增长基金的表现与风险分析.docx` | 文章审查样例文档 | `project2_finance_assistant/` |
| `stock_A~D_daily_close.csv` | 备用股票日线数据 | `data/` |

> 说明：行情数据为本地历史文件（演示用途），数据读取集中在 `function_handler.py`，接入实时行情源（akshare/tushare 等）仅需替换该读取函数。

向量数据库（ChromaDB）首次初始化后持久化到 `project2_finance_assistant/db_data/` 目录。

## 使用说明

### 阶段二（主系统，推荐）

**方式一：一键启动**

```bash
cd project2_finance_assistant
source venv/bin/activate
bash ../start_servers.sh
# 脚本会先后台启动 4 个 MCP Server，再让你选择主程序入口
# 日志输出到 logs/ 目录
```

**方式二：手动分步启动**

```bash
cd project2_finance_assistant
source venv/bin/activate

# 1. 后台启动 4 个 MCP Server
python turn_human_server.py &         # 8335
python stock_predict_mcp_server.py &  # 8336
python article_check_mcp_server.py &  # 9330
python finance_consult_mcp_server.py & # 9339

# 2. 启动主程序（三选一）
python finance_assistant_main.py                    # 命令行交互
uvicorn chat_api:app --host 0.0.0.0 --port 9998     # FastAPI 接口
python gradio_demo.py                               # Gradio 前端
```

> Gradio 前端默认仅局域网可访问；`share=True` 的公网穿透链接默认关闭，确有需要时用 `GRADIO_SHARE=1 python gradio_demo.py` 显式开启。

### 阶段一（独立子项目）

```bash
cd project1_stock_counselor
source venv/bin/activate

# 后台启动 3 个 MCP Server
python turn_human_server.py &     # 7335
python stock_sever.py &           # 7336
python policy_reply_server.py &   # 7337

# 启动 MCP Client 主程序
python multi_sse_mcp_client.py
```

### 测试话术示例

| 场景 | 输入示例 |
|---|---|
| 查询股价 | `我想咨询一下近期上证指数的收盘价` |
| 股价预测 | `顺带预测一下未来的趋势` |
| 生成报告 | `好的，生成报告吧` |
| 文章审查 | `从专业性角度检查《全球增长基金的表现与风险分析.docx》` |
| 金融咨询 | `金融经济学有什么好看的书推荐` |
| 转人工 | `转人工` |

## LLM 服务商切换

系统通过环境变量 `LLM_PROVIDER` 灵活切换驱动模型，**只需配置所选厂商的一个 API Key**：

| 选择 | `.env` 配置 | 需要的 Key | 说明 |
|---|---|---|---|
| 用通义千问 | `LLM_PROVIDER=qwen` | `API_KEY` | 全套功能可用（对话 + 向量化），默认推荐 |
| 用 DeepSeek | `LLM_PROVIDER=deepseek` | `DEEPSEEK_API_KEY` | 对话由 DeepSeek 驱动 |

> **注意**：本地 RAG 检索（Consult Agent 知识库向量化）依赖通义 `text-embedding-v1`，DeepSeek 不提供向量模型。选 `deepseek` 时若需用 RAG 功能，仍需额外配置 `API_KEY`；不用 RAG 则无需。
>
> 百炼联网检索（`APP_API_KEY`/`APP_ID`）始终为可选项，不填仅影响 `Consult Agent` 的联网检索工具，其余功能正常。

**API Key 获取方式：**
- `API_KEY`（阿里云 DashScope）：[百炼控制台](https://bailian.console.aliyun.com/) → API-KEY 管理 → 创建
- `DEEPSEEK_API_KEY`（DeepSeek）：[DeepSeek 开放平台](https://platform.deepseek.com/) → API Keys → 创建（须为官网 key 以支持 function calling）
- `APP_API_KEY`/`APP_ID`（阿里云百炼应用）：百炼控制台创建应用（接入联网搜索能力）→ 获取

## 部署

### 本机部署

参见 [使用说明](#使用说明)，`server_url` 填 `127.0.0.1`。

### 远程服务器部署

若 MCP Server 部署在远程服务器，将 `.env` 中 `server_url` 改为对应公网 IP：

```bash
server_url=your.server.ip
```

MCP Server 各端口需在防火墙放行：8335 / 8336 / 9330 / 9339。后台启动命令：

```bash
cd project2_finance_assistant
source venv/bin/activate
nohup python turn_human_server.py > logs/turn_human.log 2>&1 &
nohup python stock_predict_mcp_server.py > logs/stock_predict.log 2>&1 &
nohup python article_check_mcp_server.py > logs/article_check.log 2>&1 &
nohup python finance_consult_mcp_server.py > logs/finance_consult.log 2>&1 &
nohup uvicorn chat_api:app --host 0.0.0.0 --port 9998 --workers 1 > logs/api.log 2>&1 &
```

## 测试与评测

| 类别 | 入口 | 说明 |
|---|---|---|
| 端到端业务回归 | `python tests/run_business_demo.py` | 跑通金融问答 + 股票分析两条业务链；含 `rag_probe` 探针直查向量库输出召回片段与相似度 |
| 多用户会话测试 | `python tests/test_multi_user.py` | 自动创建双 Session，断言上下文沿用、会话隔离、业务切换三类行为；结果归档 `docs/run_logs/` |
| 预测精度回测 | `python metrics/quantify_ema_backtest.py` | 无需 API Key；EMA 滚动回测，输出 MAE/RMSE/MAPE/方向准确率 |
| 工程规模统计 | `python metrics/quantify_static.py` | 无需 API Key；AST 解析统计 Server/工具/连接/接口数量 |
| 过程文档 | `docs/run_results.md`、`docs/test_results.md`、`docs/debug_log.md` | 真实运行指标、测试结论与三次故障的"现象→定位→修复→复测"闭环记录 |

## FAQ

**Q: 启动报 `未找到 API KEY` 怎么办？**
检查 `.env` 中 `LLM_PROVIDER` 与对应 Key 是否匹配。`qwen` 模式填 `API_KEY`，`deepseek` 模式填 `DEEPSEEK_API_KEY`。确认 `project2_finance_assistant/.env` 也已同步配置（`function_handler.py` 从该路径加载）。

**Q: Agent 工具调用失败 / 不触发 function calling？**
若用 DeepSeek，必须使用官网 key，第三方平台接入的 DeepSeek 不支持 function calling。建议改用 `LLM_PROVIDER=qwen` 验证。

**Q: `finance_consult_mcp_server` 启动报 chromadb 相关错误？**
确认安装了 `chromadb==1.0.8`（高版本可能不兼容）。首次运行需向向量库灌入知识（见 [快速开始](#快速开始) 末尾"知识库初始化"），之后持久化到 `db_data/` 无需重复。

**Q: 连接 MCP Server 超时？**
确认 4 个 MCP Server 已先后台启动并监听对应端口（8335/8336/9330/9339）。检查 `.env` 中 `server_url` 是否正确，本机运行填 `127.0.0.1`。

**Q: 两个阶段能同时运行吗？**
可以，端口互不冲突（阶段一用 7335/7336/7337，阶段二用 8335/8336/9330/9339）。但需各自激活对应的虚拟环境。

## License

[MIT](LICENSE)
