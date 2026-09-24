"""
静态工程量化脚本（无需 API Key / 无需启动服务，纯本地运行）

用途：统计 MCP 多智能体金融助理系统的工程规模与组件数量，产出项目量化指标。

统计维度：
  1. 源码文件数 / 代码行数
  2. MCP Server 数量（FastMCP 实例）
  3. MCP 工具数量（@mcp.tool() 装饰器）
  4. 智能体数量（Agent 实例）
  5. MCP SSE 客户端连接数（MCPServerSse 实例）
  6. FastAPI 接口数量（@app.get/post 等）
  7. 智能体 handoff 转接关系数

运行：python3 quantify_static.py
输出：project_metrics.json + 控制台汇总
"""
import ast
import json
from pathlib import Path

# 项目根目录（本脚本位于 metrics/ 下）
ROOT = Path(__file__).resolve().parent.parent

# 两个子项目源码目录
SUBPROJECTS = {
    "project1_stock_counselor": ROOT / "project1_stock_counselor",
    "project2_finance_assistant": ROOT / "project2_finance_assistant",
}

# 需要排除的目录
EXCLUDE_DIRS = {"venv", "__pycache__", "node_modules", "db_data", "logs", ".git", ".vscode"}


def iter_py_files(base: Path):
    """递归列出 base 下所有 .py 文件，排除依赖/缓存目录。"""
    for p in base.rglob("*.py"):
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        yield p


def _is_decorator_call(node, name_attr, base_name=None):
    """判断装饰器是否为 `@base.tool()` / `@name_attr()` 形式。"""
    # @mcp.tool()
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == name_attr:
            if base_name is None:
                return True
            # 校验 base 名称，如 mcp / app
            if isinstance(node.func.value, ast.Name) and node.func.value.id == base_name:
                return True
    return False


def analyze_file(path: Path) -> dict:
    """对单个源码文件做 AST 统计。"""
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            source = path.read_text(encoding="gbk", errors="ignore")
        except Exception:
            return {}
    lines = source.splitlines()
    total_lines = len(lines)
    code_lines = sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("#"))

    stats = {
        "mcp_servers": 0,
        "mcp_tools": 0,
        "function_tools": 0,
        "agents": 0,
        "sse_clients": 0,
        "api_endpoints": 0,
        "handoffs": 0,
    }
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"total_lines": total_lines, "code_lines": code_lines, **stats}

    for node in ast.walk(tree):
        # 函数/异步函数的装饰器
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if _is_decorator_call(dec, "tool", base_name="mcp"):
                    stats["mcp_tools"] += 1
                if _is_decorator_call(dec, "tool", base_name=None):
                    # 已在上面判断过 mcp.tool，这里避免重复：仅统计非 mcp 的 .tool
                    pass
                # @function_tool 或 @function_tool()
                if isinstance(dec, ast.Name) and dec.id == "function_tool":
                    stats["function_tools"] += 1
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "function_tool":
                    stats["function_tools"] += 1
                # @app.get / @app.post / @app.route 等
                if isinstance(dec, (ast.Attribute, ast.Call)):
                    func = dec.func if isinstance(dec, ast.Call) else dec
                    if isinstance(func, ast.Attribute):
                        if isinstance(func.value, ast.Name) and func.value.id == "app":
                            if func.attr in {"get", "post", "put", "delete", "route", "patch"}:
                                stats["api_endpoints"] += 1

        # 各类实例化调用
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name == "FastMCP":
                    stats["mcp_servers"] += 1
                elif name == "Agent":
                    stats["agents"] += 1
                elif name == "MCPServerSse":
                    stats["sse_clients"] += 1
            # handoffs= 关键字参数
            for kw in node.keywords:
                if kw.arg == "handoffs":
                    stats["handoffs"] += 1

    stats["total_lines"] = total_lines
    stats["code_lines"] = code_lines
    return stats


def main():
    per_project = {}
    grand = {
        "files": 0, "total_lines": 0, "code_lines": 0,
        "mcp_servers": 0, "mcp_tools": 0, "function_tools": 0,
        "agents": 0, "sse_clients": 0, "api_endpoints": 0, "handoffs": 0,
    }

    for proj_name, proj_dir in SUBPROJECTS.items():
        files = list(iter_py_files(proj_dir))
        proj_stat = {k: 0 for k in grand if k != "files"}
        proj_stat["files"] = len(files)
        proj_files_detail = []
        for f in sorted(files):
            s = analyze_file(f)
            proj_files_detail.append({"file": f.name, **s})
            for k in s:
                if k in proj_stat:
                    proj_stat[k] += s[k]
        per_project[proj_name] = {
            "summary": proj_stat,
            "files": proj_files_detail,
        }
        grand["files"] += proj_stat["files"]
        for k in proj_stat:
            if k != "files":
                grand[k] += proj_stat[k]

    result = {
        "project": "MCP 多智能体金融助理系统",
        "summary": grand,
        "per_project": {
            name: v["summary"] for name, v in per_project.items()
        },
    }

    out_path = Path(__file__).parent / "project_metrics.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=" * 60)
    print("静态工程量化结果")
    print("=" * 60)
    print(f"源码文件数        : {grand['files']}")
    print(f"代码总行数        : {grand['total_lines']}")
    print(f"有效代码行数      : {grand['code_lines']}")
    print(f"MCP Server 数量   : {grand['mcp_servers']}")
    print(f"MCP 工具数量      : {grand['mcp_tools']}")
    print(f"本地 function_tool: {grand['function_tools']}")
    print(f"智能体 Agent 数量 : {grand['agents']}")
    print(f"MCP SSE 客户端    : {grand['sse_clients']}")
    print(f"FastAPI 接口数    : {grand['api_endpoints']}")
    print(f"handoff 转接关系  : {grand['handoffs']}")
    print("=" * 60)
    print(f"结果已写入: {out_path}")


if __name__ == "__main__":
    main()
