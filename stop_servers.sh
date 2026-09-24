#!/bin/bash
# ============================================================
# 一键关闭所有 MCP Server 与主程序进程
# 用法: bash stop_servers.sh
# ============================================================

echo "==== 关闭 Project2 的 MCP Server 与主程序 ===="

# 需要关闭的进程关键字(对应启动脚本中的 python 文件名)
TARGETS=(
    "turn_human_server.py"
    "stock_predict_mcp_server.py"
    "article_check_mcp_server.py"
    "finance_consult_mcp_server.py"
    "finance_assistant_main.py"
    "multi_user_finance_assistant_main_with_session.py"
    "chat_api:app"
    "gradio_demo.py"
)

killed=0
for target in "${TARGETS[@]}"; do
    # 查找匹配的进程 PID
    pids=$(pgrep -f "$target" 2>/dev/null)
    if [ -n "$pids" ]; then
        echo "关闭 [$target] pid=$pids"
        kill $pids 2>/dev/null
        killed=$((killed + 1))
    fi
done

# 再按端口兜底检查(8335/8336/9330/9339/9996/9998)
PORTS=(8335 8336 9330 9339 9996 9998)
for port in "${PORTS[@]}"; do
    pid=$(lsof -ti :$port 2>/dev/null || ss -lntp 2>/dev/null | grep ":$port " | awk '{print $NF}' | grep -oP '\d+' | head -1)
    if [ -n "$pid" ]; then
        echo "端口 $port 仍被占用 pid=$pid，强制关闭"
        kill -9 $pid 2>/dev/null
        killed=$((killed + 1))
    fi
done

if [ $killed -eq 0 ]; then
    echo "未发现运行中的 MCP Server 或主程序进程"
else
    echo "已关闭 $killed 个进程"
fi

echo "==== 完成 ===="
