#!/bin/bash
# ============================================================
# 多 MCP 多智能体金融助手 一键启动脚本
# 使用前请先: cp .env.example .env 并填写真实 API Key
# 然后运行: bash start_servers.sh
# ============================================================
set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
P2="$ROOT_DIR/project2_finance_assistant"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

# 自动激活项目二虚拟环境(若未激活)
if [ -f "$P2/venv/bin/activate" ]; then
    source "$P2/venv/bin/activate"
    echo "已自动激活虚拟环境: $P2/venv"
else
    echo "警告: 未找到虚拟环境 $P2/venv，将使用系统 python(可能缺少依赖)"
fi

echo "==== 启动 Project2 的 4 个 MCP Server (后台) ===="
# 转人工 MCP (端口 8335)
cd "$P2" && nohup python turn_human_server.py > "$LOG_DIR/turn_human.log" 2>&1 &
echo "turn_human_server 已启动 (8335) pid=$!"
# 股价预测 MCP (端口 8336)
cd "$P2" && nohup python stock_predict_mcp_server.py > "$LOG_DIR/stock_predict.log" 2>&1 &
echo "stock_predict_mcp_server 已启动 (8336) pid=$!"
# 文章审查 MCP (端口 9330)
cd "$P2" && nohup python article_check_mcp_server.py > "$LOG_DIR/article_check.log" 2>&1 &
echo "article_check_mcp_server 已启动 (9330) pid=$!"
# 金融咨询 MCP (端口 9339)
cd "$P2" && nohup python finance_consult_mcp_server.py > "$LOG_DIR/finance_consult.log" 2>&1 &
echo "finance_consult_mcp_server 已启动 (9339) pid=$!"

echo "等待 MCP Server 初始化..."
sleep 8

echo ""
echo "==== 选择主程序入口 ===="
echo "1) 命令行交互: finance_assistant_main.py"
echo "2) FastAPI 接口: chat_api.py (端口 9998)"
echo "3) Gradio 前端 : gradio_demo.py (端口 9996)"
echo "4) 仅启动 MCP Server,不启动主程序"
read -p "请输入序号 [1-4]: " choice

case $choice in
  1)
    cd "$P2" && python finance_assistant_main.py
    ;;
  2)
    cd "$P2" && uvicorn chat_api:app --host 0.0.0.0 --port 9998 --workers 1
    ;;
  3)
    cd "$P2" && python gradio_demo.py
    ;;
  4)
    echo "MCP Server 已在后台运行,日志位于 $LOG_DIR"
    ;;
  *)
    echo "无效输入,退出。MCP Server 仍在后台运行。"
    ;;
esac
