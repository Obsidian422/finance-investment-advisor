#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
投资政策 RAG 检索评测

用途
----
把「RAG 效果还行」变成可复现的数字。分两层：

  第一层 · 检索指标（只需 embedding，便宜、快）
      Hit@1 / Hit@5 / Recall@5 / MRR —— in_scope 与 paraphrase 题
      拒答正确率 + 误召最高相似度 —— out_of_scope 题
  第二层 · LLM-as-judge（可选，--judge，另需 LLM 调用）
      Faithfulness（答案是否只依据召回片段）与 Answer Relevance（是否答到点上），1–5 分

为什么这么设计
--------------
· 召回与生成分开评。生成答错但召回对了，和召回就错了，是两类完全不同的 bug，
  混在一起看总分定位不了问题。
· 拒答单列。这个系统的关键设计之一是「未命中显式拒答」，不测就等于没验证。
· 阈值取线上真实值 0.5（finance_consult_mcp_server.py:176），不是拍脑袋的数。

用法
----
    cd project2_finance_assistant
    python eval/run_eval.py                 # 只跑检索指标
    python eval/run_eval.py --judge         # 追加 LLM-as-judge
    python eval/run_eval.py --limit 10      # 抽样跑通流程

需要 .env 里配好 API_KEY（向量化用；--judge 时 LLM 也用这一个）。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))          # 复用项目自己的实现，不另写一套

import pandas as pd  # noqa: E402

from finance_consult_mcp_server import ChromaDBWithQwen  # noqa: E402

POLICY_XLSX = PARENT / "投资政策.xlsx"
GOLDEN = HERE / "golden_set.json"

ONLINE_THRESHOLD = 0.5   # 与线上一致


# --------------------------------------------------------------------------
# 知识库
# --------------------------------------------------------------------------
def ensure_kb(db: ChromaDBWithQwen, policy_texts: list[str], quiet: bool = False) -> int:
    """集合为空时灌库。

    注意：原实现里灌库那三行是**注释掉**的（finance_consult_mcp_server.py:169-170），
    所以全新 clone 拉下来跑不出知识库。评测入口把这个补上，顺带修掉这个可复现性缺口。
    """
    existing = db.collection.count()
    if existing >= len(policy_texts):
        if not quiet:
            print(f"[KB] 已有 {existing} 条，跳过灌库")
        return existing

    if not quiet:
        print(f"[KB] 当前 {existing} 条，灌入 {len(policy_texts)} 条政策 …")
    db.add_documents(
        documents=policy_texts,
        ids=[f"policy_{i:02d}" for i in range(len(policy_texts))],
    )
    n = db.collection.count()
    if not quiet:
        print(f"[KB] 灌库完成，共 {n} 条")
    return n


# --------------------------------------------------------------------------
# 指标
# --------------------------------------------------------------------------
def rank_of_first_hit(docs: list[str], expects: list[str]) -> int | None:
    """第一个命中期望文档的排名（从 1 开始），没命中返回 None。"""
    for rank, doc in enumerate(docs, start=1):
        if doc in expects:
            return rank
    return None


def retrieval_metrics(hits: list[tuple[str, float]], expects: list[str],
                      threshold: float) -> dict:
    """hits: [(doc, similarity)]，按相似度降序（未过滤）。"""
    docs_all = [d for d, _ in hits]
    # 线上实际只看得到 ≥ 阈值 的片段，所以真实可用列表是过滤后的
    docs_pass = [d for d, s in hits if s >= threshold]

    rank_all = rank_of_first_hit(docs_all, expects)
    rank_pass = rank_of_first_hit(docs_pass, expects)

    return {
        "hit@1": bool(rank_all == 1),
        "hit@5": rank_all is not None,
        # 经过阈值过滤后还能不能召回 —— 这个才决定线上效果
        "hit@5_passed": rank_pass is not None,
        "mrr": (1.0 / rank_all) if rank_all else 0.0,
        "n_retrieved": len(docs_all),
        "n_passed": len(docs_pass),
        "max_similarity": max((s for _, s in hits), default=0.0),
    }


def summarize(rows: list[dict], key_prefix: str) -> dict:
    sel = [r for r in rows if r["type"] == key_prefix]
    if not sel:
        return {}
    n = len(sel)
    return {
        "n": n,
        "hit@1": round(sum(r["hit@1"] for r in sel) / n, 4),
        "hit@5": round(sum(r["hit@5"] for r in sel) / n, 4),
        "hit@5_passed": round(sum(r["hit@5_passed"] for r in sel) / n, 4),
        "mrr": round(sum(r["mrr"] for r in sel) / n, 4),
    }


# --------------------------------------------------------------------------
# LLM-as-judge
# --------------------------------------------------------------------------
ANSWER_SYS = (
    "你是基金合规助手。只能依据给定【参考资料】回答问题，"
    "资料里没有的内容不要编造，直接说明资料未覆盖。回答要简洁。"
)

JUDGE_SYS = (
    "你是严格的评测员。给定【问题】【参考资料】【答案】，按两个维度各打 1-5 分：\n"
    "faithfulness：答案中的每个事实是否都能在参考资料里找到依据。出现资料外内容即扣分。\n"
    "relevance：答案是否正面回答了问题。\n"
    "只输出一行 JSON：{\"faithfulness\": <int>, \"relevance\": <int>, \"reason\": \"<一句话>\"}"
)


def _extract_json(text: str) -> dict | None:
    import re
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


async def judge_case(question: str, context: str, answer: str) -> dict:
    from function_handler import LLM_replay

    prompt = f"【问题】{question}\n\n【参考资料】\n{context}\n\n【答案】\n{answer}"
    resp = await LLM_replay(prompt_template=JUDGE_SYS, messages=prompt)
    text = resp.choices[0].message.content
    parsed = _extract_json(text)
    if parsed:
        return {"faithfulness": parsed.get("faithfulness"),
                "relevance": parsed.get("relevance"),
                "reason": parsed.get("reason", "")}
    return {"faithfulness": None, "relevance": None, "reason": f"解析失败: {text[:80]}"}


async def answer_case(question: str, context: str) -> str:
    from function_handler import LLM_replay

    resp = await LLM_replay(
        prompt_template=ANSWER_SYS,
        messages=f"【参考资料】\n{context}\n\n【问题】{question}",
    )
    return resp.choices[0].message.content


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", action="store_true", help="追加 LLM-as-judge（慢、额外消耗）")
    ap.add_argument("--k", type=int, default=5, help="召回条数，默认 5（与线上 TOP_K 一致）")
    ap.add_argument("--threshold", type=float, default=ONLINE_THRESHOLD,
                    help=f"相似度阈值，默认 {ONLINE_THRESHOLD}（与线上一致）")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 条，用于快速验证流程")
    ap.add_argument("--out", default=str(HERE / "eval_results.json"))
    ap.add_argument("--tag", default="", help="本次运行的标签，写进结果文件")
    args = ap.parse_args()

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    cases = golden["cases"]
    if args.limit:
        cases = cases[:args.limit]

    policy_texts = pd.read_excel(POLICY_XLSX)["投资政策"].astype(str).tolist()
    idx2text = {i: t for i, t in enumerate(policy_texts)}

    print("=" * 72)
    print("投资政策 RAG 评测")
    print(f"  题目 {len(cases)} 条 | k={args.k} | 阈值={args.threshold} | judge={args.judge}")
    print("=" * 72)

    db = ChromaDBWithQwen(persist_directory=str(PARENT / "db_data"))
    ensure_kb(db, policy_texts)

    rows: list[dict] = []
    for c in cases:
        expects = [idx2text[i] for i in c["expect_ids"] if i in idx2text]

        res = db.query_by_cosine_similarity(query_texts=[c["question"]], n_results=args.k)
        docs = res["documents"][0]
        sims = res["similarities"][0]
        hits = list(zip(docs, [float(s) for s in sims]))

        row = {
            "id": c["id"],
            "type": c["type"],
            "question": c["question"],
            "expect_ids": c["expect_ids"],
            "retrieved_similarities": [round(s, 4) for _, s in hits],
        }

        if c["type"] == "out_of_scope":
            # 拒答正确 = 没有任何片段越过阈值
            best = max((s for _, s in hits), default=0.0)
            row["abstain_ok"] = best < args.threshold
            row["max_similarity"] = round(best, 4)
        else:
            row.update(retrieval_metrics(hits, expects, args.threshold))

        rows.append(row)

    # ---------------- 汇总 ----------------
    print()
    s_in = summarize(rows, "in_scope")
    s_pp = summarize(rows, "paraphrase")

    def show(title: str, s: dict):
        if not s:
            return
        print(f"[{title}] n={s['n']}")
        print(f"    Hit@1          {s['hit@1']:.2%}")
        print(f"    Hit@5          {s['hit@5']:.2%}   （未过滤，含低于阈值的片段）")
        print(f"    Hit@5（过阈值） {s['hit@5_passed']:.2%}   ← 线上真实可用召回")
        print(f"    MRR            {s['mrr']:.4f}")

    show("直接问法", s_in)
    print()
    show("同义改写", s_pp)

    oos = [r for r in rows if r["type"] == "out_of_scope"]
    if oos:
        ok = sum(r["abstain_ok"] for r in oos)
        worst = max(r["max_similarity"] for r in oos)
        print()
        print(f"[拒答 / out_of_scope] n={len(oos)}")
        print(f"    拒答正确率      {ok / len(oos):.2%}   （无片段 ≥ {args.threshold}）")
        print(f"    最高误召相似度  {worst:.4f}")
        bad = [r["id"] for r in oos if not r["abstain_ok"]]
        if bad:
            print(f"    误召题目        {bad}")

    summary = {
        "tag": args.tag,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "k": args.k,
        "threshold": args.threshold,
        "judge": args.judge,
        "n_cases": len(rows),
        "in_scope": s_in,
        "paraphrase": s_pp,
        "out_of_scope": {
            "n": len(oos),
            "abstain_accuracy": round(sum(r["abstain_ok"] for r in oos) / len(oos), 4) if oos else None,
            "max_false_positive_similarity": round(max((r["max_similarity"] for r in oos), default=0.0), 4),
        } if oos else {},
    }

    # ---------------- 可选：LLM-as-judge ----------------
    if args.judge:
        print()
        print("=" * 72)
        print("LLM-as-judge（对 in_scope + paraphrase 抽答并评分）")
        print("=" * 72)

        async def run_judge():
            out = []
            for r in rows:
                if r["type"] == "out_of_scope":
                    continue
                res = db.query_by_cosine_similarity(
                    query_texts=[r["question"]], n_results=args.k,
                    min_similarity=args.threshold)
                frags = res.get("query_results", [[]])[0]
                if not frags:
                    r["judge"] = {"faithfulness": None, "relevance": None,
                                  "reason": "无片段过阈值，按拒答处理"}
                    out.append(r)
                    continue
                ctx = "\n".join(f"- {f['document']}" for f in frags)
                r["answer"] = await answer_case(r["question"], ctx)
                r["judge"] = await judge_case(r["question"], ctx, r["answer"])
                out.append(r)
                print(f"  {r['id']}  F={r['judge']['faithfulness']}  R={r['judge']['relevance']}")
            return out

        rows = asyncio.run(run_judge())

        scored = [r for r in rows if r.get("judge", {}).get("faithfulness")]
        if scored:
            avg_f = sum(r["judge"]["faithfulness"] for r in scored) / len(scored)
            avg_r = sum(r["judge"]["relevance"] for r in scored) / len(scored)
            print()
            print(f"  平均 Faithfulness     {avg_f:.2f} / 5   (n={len(scored)})")
            print(f"  平均 Answer Relevance {avg_r:.2f} / 5")
            summary["judge_avg"] = {
                "faithfulness": round(avg_f, 3),
                "relevance": round(avg_r, 3),
                "n_scored": len(scored),
                "n_total": len([r for r in rows if r["type"] != "out_of_scope"]),
            }

    Path(args.out).write_text(
        json.dumps({"summary": summary, "cases": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print()
    print(f"明细与汇总已写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())