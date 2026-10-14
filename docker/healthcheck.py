#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""容器健康检查：确认 7 个 MCP Server 端口都在监听。

不用 curl 探 /sse —— SSE 是长连接，curl 会一直挂着不返回。
这里只做 TCP 建连，够判断进程有没有起来、有没有绑上端口。
"""
import socket
import sys

PORTS = (7335, 7336, 7337, 8335, 8336, 9330, 9339)

dead = []
for port in PORTS:
    try:
        socket.create_connection(("127.0.0.1", port), timeout=2).close()
    except OSError:
        dead.append(port)

if dead:
    print(f"未监听: {dead}", flush=True)
    sys.exit(1)

print(f"全部 {len(PORTS)} 个 MCP Server 端口正常", flush=True)