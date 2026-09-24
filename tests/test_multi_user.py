"""
多用户（多 Session）综合测试脚本
------------------------------------------------
覆盖三类测试：
  1) 多轮对话测试（Session A 第二轮"那未来一周呢？"需识别第一轮的股票名）
  2) 用户隔离测试（Session B 不应读取 Session A 的股票上下文）
  3) 业务切换测试（先金融问答，再查询股票 / 转人工，Switch Agent 正确 Handoff）

运行：
    cd tests
    ../project2_finance_assistant/venv/bin/python test_multi_user.py

输出：
    控制台实时输出 + tests/run_logs/test_multi_user.txt
"""
import asyncio
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
P2 = HERE.parent / "project2_finance_assistant"
sys.path.insert(0, str(P2))

# 复用多用户主程序的入口与会话存储
from multi_user_finance_assistant_main_with_session import chat_service, global_sessions

LOG_PATH = HERE / "run_logs" / "test_multi_user.txt"


class Logger:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(path, "w", encoding="utf-8")

    def log(self, msg=""):
        print(msg)
        self.f.write(str(msg) + "\n")
        self.f.flush()

    def close(self):
        self.f.close()


def snap(sid: str):
    """返回 (当前Agent名, 历史消息数)"""
    s = global_sessions.get(sid, {})
    agent = s.get("current_agent")
    return (agent.name if agent else None), len(s.get("messages", []))


async def ask(sid: str, msg: str):
    t0 = time.time()
    res = await chat_service(current_message=msg, session_id=sid)
    return res, time.time() - t0


async def main():
    lg = Logger(LOG_PATH)
    lg.log("=" * 72)
    lg.log("多 Session 多用户综合测试报告")
    lg.log("=" * 72)

    # ============================================================
    # 一、Session A：多轮对话测试
    # ============================================================
    lg.log("\n【一、Session A — 多轮对话测试】")

    res, dt = await ask("", "我想咨询一下近期上证指数的收盘价")
    sid_a = res["session_id"]
    agent, hlen = snap(sid_a)
    lg.log(f"\n[T1] 用户: 我想咨询一下近期上证指数的收盘价   (耗时 {dt:.1f}s)")
    lg.log(f"     当前Agent: {agent} | 历史消息数: {hlen}")
    lg.log(f"     AI: {res['response']}")

    res, dt = await ask(sid_a, "那未来一周呢？")
    agent, hlen = snap(sid_a)
    lg.log(f"\n[T2] 用户: 那未来一周呢？   (耗时 {dt:.1f}s)")
    lg.log(f"     当前Agent: {agent} | 历史消息数: {hlen}")
    lg.log(f"     AI: {res['response']}")
    ok_ctx = "上证指数" in res["response"]
    lg.log(f"     >> 多轮上下文检验: {'通过（正确沿用上证指数）' if ok_ctx else '需人工确认'}")

    res, dt = await ask(sid_a, "好的，生成报告吧")
    agent, hlen = snap(sid_a)
    lg.log(f"\n[T3] 用户: 好的，生成报告吧   (耗时 {dt:.1f}s)")
    lg.log(f"     当前Agent: {agent} | 历史消息数: {hlen}")
    lg.log(f"     AI: {str(res['response'])[:500]}")

    # ============================================================
    # 二、Session B：用户隔离测试
    # ============================================================
    lg.log("\n" + "-" * 72)
    lg.log("【二、Session B — 用户隔离测试】")

    res, dt = await ask("", "金融经济学有什么好看的书推荐？")
    sid_b = res["session_id"]
    agent, hlen = snap(sid_b)
    lg.log(f"\n[B1] 用户: 金融经济学有什么好看的书推荐？   (耗时 {dt:.1f}s)")
    lg.log(f"     当前Agent: {agent} | 历史消息数: {hlen}")
    lg.log(f"     AI: {str(res['response'])[:500]}")

    # ---- 关键隔离验证：B 第二轮回问句，不应认识 A 中的"上证指数" ----
    res, dt = await ask(sid_b, "那未来一周呢？")
    agent, hlen = snap(sid_b)
    lg.log(f"\n[B2] 用户: 那未来一周呢？   (耗时 {dt:.1f}s)")
    lg.log(f"     当前Agent: {agent} | 历史消息数: {hlen}")
    lg.log(f"     AI: {str(res['response'])[:500]}")
    leaked = "上证指数" in str(res["response"])
    lg.log(f"     >> 用户隔离检验: {'异常（Session B 读到了 Session A 的股票上下文）' if leaked else '通过（未读到 Session A 的股票上下文）'}")

    # ---- 会话内容隔离对比 ----
    a_msgs = str(global_sessions.get(sid_a, {}).get("messages", []))
    b_msgs = str(global_sessions.get(sid_b, {}).get("messages", []))
    lg.log(f"\n[隔离对比] Session A 历史消息数={len(global_sessions.get(sid_a, {}).get('messages', []))}，"
           f"Session B 历史消息数={len(global_sessions.get(sid_b, {}).get('messages', []))}")
    lg.log(f"[隔离对比] Session A 历史含'上证指数': {'上证指数' in a_msgs}")
    lg.log(f"[隔离对比] Session B 历史含'上证指数': {'上证指数' in b_msgs}")

    # ============================================================
    # 三、业务切换测试
    # ============================================================
    lg.log("\n" + "-" * 72)
    lg.log("【三、业务切换测试】")

    # Session A：从股票分析（Investment）切换到转人工（Human）
    res, dt = await ask(sid_a, "我不满意，转人工服务")
    agent, hlen = snap(sid_a)
    lg.log(f"\n[A-switch] 用户: 我不满意，转人工服务   (耗时 {dt:.1f}s)")
    lg.log(f"     当前Agent: {agent} | 历史消息数: {hlen}")
    lg.log(f"     AI: {str(res['response'])[:500]}")
    lg.log(f"     >> 业务切换检验: 当前Agent={agent}（期望 Handoff 至 turn_human Agent）")

    # Session B：先金融问答（Consult）→ 再查股票（Investment）
    res, dt = await ask(sid_b, "顺便帮我查一下中国石油的近期收盘价")
    agent, hlen = snap(sid_b)
    lg.log(f"\n[B-switch] 用户: 顺便帮我查一下中国石油的近期收盘价   (耗时 {dt:.1f}s)")
    lg.log(f"     当前Agent: {agent} | 历史消息数: {hlen}")
    lg.log(f"     AI: {str(res['response'])[:500]}")
    lg.log(f"     >> 业务切换检验: 当前Agent={agent}（期望 Handoff 至 Investment Agent）")

    # ============================================================
    # 汇总
    # ============================================================
    lg.log("\n" + "=" * 72)
    lg.log("测试汇总")
    lg.log("=" * 72)
    lg.log(f"Session A id = {sid_a}")
    lg.log(f"Session B id = {sid_b}")
    lg.log(f"多轮对话（T2 识别上证指数）: {'通过' if ok_ctx else '未通过'}")
    lg.log(f"用户隔离（B 未读到 A 上下文）: {'通过' if not leaked else '未通过'}")
    lg.log("详细结果见本文件。")
    lg.close()


if __name__ == "__main__":
    asyncio.run(main())
