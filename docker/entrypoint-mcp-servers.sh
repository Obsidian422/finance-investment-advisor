#!/usr/bin/env bash
# =============================================================================
# 在单个容器里拉起全部 7 个 MCP Server。
#
# 端口分配（与各 server 源码里的 FastMCP(host="0.0.0.0", port=...) 一致）：
#   project1_stock_counselor   转人工 7335 | 行情/EMA 7336 | 政策问答 7337
#   project2_finance_assistant 转人工 8335 | 股价预测 8336 | 文章审查 9330 | 金融咨询(RAG) 9339
#
# 任一 Server 退出即整体退出（容器重启策略会拉起），避免「半死不活」的状态 ——
# 这正是 start_servers.sh 在裸机上靠端口/进程名双重清理要解决的问题。
# =============================================================================
set -euo pipefail

cd /app
LOG_DIR=/app/logs
mkdir -p "$LOG_DIR"

pids=()

start() {
    local dir="$1" script="$2" log="$3"
    ( cd "/app/$dir" && exec python "$script" ) > "$LOG_DIR/$log" 2>&1 &
    pids+=("$!")
    echo "[start] $(basename "$dir")/$script  pid=$!  log=$LOG_DIR/$log"
}

echo "==== 启动 7 个 MCP Server ===="
start project1_stock_counselor   turn_human_server.py         p1_turn_human.log
start project1_stock_counselor   stock_sever.py               p1_stock.log
start project1_stock_counselor   policy_reply_server.py       p1_policy.log
start project2_finance_assistant turn_human_server.py         p2_turn_human.log
start project2_finance_assistant stock_predict_mcp_server.py  p2_stock_predict.log
start project2_finance_assistant article_check_mcp_server.py  p2_article_check.log
start project2_finance_assistant finance_consult_mcp_server.py p2_finance_consult.log

cleanup() {
    echo "[signal] 收到退出信号，停止全部 Server"
    for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
    wait || true
}
trap cleanup TERM INT

echo "==== 等待 Server 就绪 ===="
sleep 8
echo "全部 7 个 Server 已拉起，进入守护状态"

# 任一 Server 挂掉就整体退出，交给 compose 的 restart 策略
wait -n
status=$?
echo "[fatal] 有 MCP Server 退出 (status=$status)，容器结束"
cleanup
exit 1