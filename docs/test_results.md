# 多用户与综合测试结果

> 测试脚本：`test_multi_user.py`（自动创建两个 Session 并执行三类测试）
> 原始日志：`docs/run_logs/test_multi_user.txt`

---

## 测试概览

| 项 | 值 |
|---|---|
| Session A id | `c0782144-f162-4e9b-8307-b05bda0676c8` |
| Session B id | `0298406d-8223-466c-930e-9dfcab20277a` |
| 会话存储 | `global_sessions = {session_id: {messages, current_agent, user_id}}` |
| 结论 | 多轮对话 ✅ 通过 ｜ 用户隔离 ✅ 通过 ｜ 业务切换 ✅ 通过 |

---

## 一、多轮对话测试（Session A）

| 轮次 | 用户输入 | 当前 Agent | 历史消息数 | 结果 |
|---|---|---|---|---|
| T1 | 我想咨询一下近期上证指数的收盘价 | Investment Agent | 9 | 正确查询：79.64 / 73.76 / 77.62，近三天均值 77.007，判定下跌 |
| T2 | **那未来一周呢？** | Investment Agent | 15 | **正确沿用"上证指数"**，给出未来 7 天预测（81.761, 80.052, 75.01, 77.102×4） |
| T3 | 好的，生成报告吧 | Investment Agent | 21 | 生成《上证指数投资建议分析报告》 |

> ✅ **T2 未出现股票名，系统仍正确识别出上一轮的"上证指数"** —— 多轮上下文生效。

---

## 二、用户隔离测试（Session B）

| 轮次 | 用户输入 | 当前 Agent | 历史消息数 | 结果 |
|---|---|---|---|---|
| B1 | 金融经济学有什么好看的书推荐？ | Consult Agent | 14 | 金融问答正常（本地/联网综合） |
| B2 | **那未来一周呢？** | Consult Agent | 17 | 回答"请问您提到的'未来一周'具体是指什么呢？" —— **未读到 Session A 的股票上下文** |

**隔离对比：**

| 指标 | Session A | Session B |
|---|---|---|
| 历史消息数 | 21 | 17 |
| 历史是否含"上证指数" | **True** | **False** |

> ✅ **Session B 未读取 Session A 的股票上下文** —— 两个 Session 的消息历史相互隔离。

---

## 三、业务切换测试

| 场景 | Session | 用户输入 | 切换结果（当前 Agent） | 预期 | 结果 |
|---|---|---|---|---|---|
| 股票分析 → 转人工 | A | 我不满意，转人工服务 | **turn_human Agent** | 转人工 | ✅ |
| 金融问答 → 股票查询 | B | 顺便帮我查一下中国石油的近期收盘价 | **Investment Agent** | 股票分析 | ✅ |

> ✅ **Switch Agent 正确完成 Handoff**，且切换后 `current_agent` 正确更新。

---

## 四、重点观察项

| 观察项 | 结果 |
|---|---|
| 不同 Session 消息历史是否隔离 | ✅ 隔离（A/B 的 `messages` 独立） |
| 当前 Agent 是否随 Handoff 正确更新 | ✅ 更新（A 转人工后为 turn_human Agent；B 切股票后为 Investment Agent） |
| 多轮对话能否使用上一轮上下文 | ✅ 能（T2 识别上证指数） |
| Switch Agent 是否分流到正确专业 Agent | ✅ 正确（Investment / Consult / turn_human） |
| MCP 工具结果是否返回给对应用户 | ✅ 正确（收盘价、预测、报告均返回对应 Session） |

---

## 测试结论

两个 Session 的多轮对话、用户隔离与业务切换三类测试**全部通过**：
- 消息历史按 `session_id` 严格隔离；
- `current_agent` 随 handoff 正确流转；
- 多轮上下文可跨轮沿用；
- Switch Agent 分流准确，MCP 工具结果正确回传。

> 完整原始日志见：`run_logs/test_multi_user.txt`
