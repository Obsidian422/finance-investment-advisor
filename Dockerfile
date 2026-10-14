# =============================================================================
# 多智能体金融投资助理 —— 单镜像
#
# 同一个镜像同时用于 MCP Server 与主应用：
#   · mcp-servers 服务：在容器内拉起全部 7 个 FastMCP Server
#   · app 服务：FastAPI 多用户会话接口（:9998）
#   · gradio 服务：Gradio 前端（:9996）
#
# 为什么 7 个 Server 放同一个容器：代码里所有 Server 地址都拼成
#   http://{server_url}:<port>/sse
# server_url 是「单个值」，7 个 Server 靠端口区分 —— 必须处于同一主机名下。
# 拆成 7 个容器后单一 server_url 无法同时指向 7 个不同的 hostname。
# 应用侧跨容器访问时把 server_url 指向 mcp-servers 服务名即可（见 docker-compose.yml）。
# =============================================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

# 先单独装依赖，让这一层能被缓存复用
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 7 个 MCP Server 端口 + FastAPI(9998) + Gradio(9996)
EXPOSE 7335 7336 7337 8335 8336 9330 9339 9998 9996

# 默认拉起全部 MCP Server；主应用在 compose 里用 command 覆盖
CMD ["bash", "docker/entrypoint-mcp-servers.sh"]