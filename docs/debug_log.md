# 真实问题调试记录

> 记录本次运行过程中**真实发生**的问题及其排查闭环（含问题现象、所在模块、排查与修改、修改后结果）。

---

## 问题一：重复启动 MCP Server 报端口占用（address already in use）

### 1. 问题现象
重复执行启动命令后，`logs/*.log` 中出现：
```
ERROR:    [Errno 98] error while attempting to bind on address ('0.0.0.0', 8335): address already in use
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
```
四个 MCP Server（8335/8336/9330/9339）**全部启动失败并立即退出**，主程序无法连接。

### 2. 问题所在模块
MCP Server 启动层（`FastMCP(...).run(transport='sse')` 的端口绑定），根因是**端口已被既有进程占用**。

### 3. 排查与修改
```bash
# 1) 查看端口占用与对应 PID
ss -lntp | grep -E ':(8335|8336|9330|9339)'
# 输出：0.0.0.0:9339 pid=50859 / 9330 pid=50857 / 8336 pid=50855 / 8335 pid=50853
```
排查结论：端口已被**此前已启动的 4 个 Server 进程**占用，属于"重复启动"导致的冲突，Server 本身健康。

修改策略（二选一）：
- **复用**：检测到端口已监听，直接复用既有 Server，不再重复启动；
- **重启**：先 `bash stop_servers.sh`（或 `kill <pid>`）释放端口，再重新启动。

本次采用**复用既有 Server**方案，避免误杀正常服务。

### 4. 修改后结果
确认 4 个端口均处于 LISTEN 状态后，主程序成功连接并完成后续两类业务运行，问题消除。

---

## 问题二：LLM 调用返回 403 —— 免费额度耗尽（FreeTierOnly）

### 1. 问题现象
所有 LLM 对话调用立即失败（耗时 <1s），返回：
```
Error code: 403 - {'error': {'message': 'Free quota exhausted. To continue accessing the model on a
paid basis, please add funds or disable the "use free tier only" mode in the management console.',
'type': 'AllocationQuota.FreeTierOnly'}}
```
表现为：**MCP Server 正常、本地 RAG 检索正常（embedding 可用），但对话生成全部失败**。

### 2. 问题所在模块
LLM 服务层（`function_handler.LLM_replay` → `AsyncOpenAI.chat.completions.create`）。根因是**通义千问账号处于"仅免费额度"模式且免费额度已耗尽**，属账号侧配额问题，非代码缺陷。

### 3. 排查与修改
- 定位：错误码 `AllocationQuota.FreeTierOnly` 明确指向账号配额；同一 `API_KEY` 的 embedding 调用仍成功，说明 Key 有效、仅对话额度耗尽。
- 修改：在阿里云百炼控制台**充值 / 关闭"仅免费额度"模式**（账号侧操作）。
- 验证：先用单轮对话做冒烟测试确认恢复。

### 4. 修改后结果
冒烟测试返回 `STATUS success`（"你好！很高兴为你服务！😊"），随后两类业务与多用户测试全部正常跑通。

---

## 问题三：多实例并发写同一日志导致内容乱码

### 1. 问题现象
运行日志中出现乱码与错行，例如：
```
【Agent 回答】(耗时 27.7s)   →   显示为   ��）\n答】(耗时 27.7s)
```

### 2. 问题所在模块
测试脚本的日志写入层（`Logger` 以 `"w"` 模式打开同一日志文件）。根因是**多个脚本实例被重复启动，并发写同一文件**（多次后台启动未去重）。

### 3. 排查与修改
```bash
# 查看重名运行实例
pgrep -af "run_business_dem[o].py|test_multi_use[r].py"
# 清理全部重复实例（注意：pkill -f 会匹配到自身 shell，需用括号技巧避免自匹配）
pkill -f "run_business_demo.py"; pkill -f "test_multi_user.py"
```
修改策略：**先清理重复进程，再以单实例顺序运行**（B → C），并在启动前删除旧日志。

### 4. 修改后结果
日志内容完整、无乱码，两次运行结果清晰可读（见 `run_logs/run_business.txt`、`run_logs/test_multi_user.txt`）。

---

## 小结

| # | 问题 | 模块 | 根因 | 处理 | 结果 |
|---|---|---|---|---|---|
| 1 | 端口占用 `address already in use` | MCP Server 启动 | 重复启动、端口被既有进程占用 | 端口检测后复用/重启 | 恢复 |
| 2 | LLM 403 `FreeTierOnly` | LLM 服务层 | 账号免费额度耗尽 | 控制台充值/关闭免费模式 | 恢复 |
| 3 | 日志乱码 | 测试脚本日志层 | 多实例并发写同一文件 | 清理重复实例、单实例运行 | 恢复 |
