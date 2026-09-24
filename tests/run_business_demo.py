"""
端到端业务回归脚本（两类业务）
------------------------------------------------
业务一：金融知识问答（Consult Agent → 本地 RAG 检索，未命中回退联网检索）
业务二：股票投资分析（Investment Agent → 查询趋势 → 预测 → 生成报告 → 风险提示）

同时记录 RAG 细节：Top K、最低相似度阈值、实际召回知识片段、是否触发联网检索。

运行：
    cd tests
    ../project2_finance_assistant/venv/bin/python run_business_demo.py

输出：
    控制台 + tests/run_logs/run_business.txt
"""
import asyncio
import contextlib
import io
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
P2 = HERE.parent / "project2_finance_assistant"
sys.path.insert(0, str(P2))

from multi_user_finance_assistant_main_with_session import chat_service, global_sessions

LOG_PATH = HERE / "run_logs" / "run_business.txt"

# RAG 检索参数（与 finance_consult_mcp_server.py 中的实现一致）
TOP_K = 5
MIN_SIMILARITY = 0.5


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


async def ask(sid: str, msg: str):
    t0 = time.time()
    res = await chat_service(current_message=msg, session_id=sid)
    return res, time.time() - t0


def rag_probe(question: str):
    """直接调用底层 RAG，返回命中片段（含相似度）。"""
    # 抑制被 import 模块的打印噪声
    with contextlib.redirect_stdout(io.StringIO()):
        from finance_consult_mcp_server import qwen_db  # noqa
    res = qwen_db.query_by_cosine_similarity(
        query_texts=[question], n_results=TOP_K, min_similarity=MIN_SIMILARITY
    )
    qr = res.get("query_results", [[]])
    return qr[0] if qr else []


async def main():
    lg = Logger(LOG_PATH)
    lg.log("=" * 72)
    lg.log("端到端业务运行结果（金融知识问答 / 股票投资分析）")
    lg.log("=" * 72)

    # ============================================================
    # 业务一：金融知识问答
    # ============================================================
    lg.log("\n" + "=" * 72)
    lg.log("业务一：金融知识问答（Consult Agent → 本地 RAG / 联网兜底）")
    lg.log("=" * 72)

    questions = [
        "禁止投资于哪些行业？",            # 预期命中本地知识库
        "金融经济学有什么好看的书推荐？",   # 预期未命中 → 联网检索
    ]

    for q in questions:
        lg.log(f"\n【问题】{q}")
        lg.log(f"【RAG 参数】Top K = {TOP_K}，最低相似度阈值 = {MIN_SIMILARITY}")

        hits = rag_probe(q)
        if hits:
            lg.log(f"【本地召回】命中 {len(hits)} 条（相似度≥{MIN_SIMILARITY}）：")
            for i, h in enumerate(hits, 1):
                doc = str(h.get("document", "")).replace("\n", " ")
                sim = h.get("similarity")
                lg.log(f"    {i}. [相似度 {sim:.3f}] {doc[:120]}")
            lg.log("【是否触发联网检索】否（本地已命中）")
        else:
            lg.log("【本地召回】未命中任何片段（相似度均低于阈值）")
            lg.log("【是否触发联网检索】是（本地无可靠答案，回退百炼联网检索工具）")

        res, dt = await ask("", q)
        lg.log(f"【Agent 回答】(耗时 {dt:.1f}s)")
        lg.log(f"    {res['response']}")

    # ============================================================
    # 业务二：股票投资分析
    # ============================================================
    lg.log("\n" + "=" * 72)
    lg.log("业务二：股票投资分析（Investment Agent → 查询趋势 → 预测 → 报告 → 风险提示）")
    lg.log("=" * 72)

    steps = [
        "我想咨询一下近期中国石油的收盘价",
        "顺带预测一下未来的趋势",
        "好的，生成报告吧",
    ]
    sid = ""
    for i, q in enumerate(steps, 1):
        res, dt = await ask(sid, q)
        sid = res["session_id"]
        s = global_sessions.get(sid, {})
        agent = s.get("current_agent")
        agent_name = agent.name if agent else None
        lg.log(f"\n【步骤 {i}】用户: {q}   (耗时 {dt:.1f}s)")
        lg.log(f"    当前Agent: {agent_name}")
        lg.log(f"    AI: {str(res['response'])[:800]}")

    lg.log("\n" + "=" * 72)
    lg.log("运行结束")
    lg.log("=" * 72)
    lg.close()


if __name__ == "__main__":
    asyncio.run(main())
