#%%
"""
一个 MCP client实现多个 MCP server的工具调用
"""
import json
import os
from mcp.client.sse import sse_client  #sse_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.stdio import stdio_client
from mcp import ClientSession
from openai import AsyncOpenAI
from dotenv import load_dotenv
from contextlib import AsyncExitStack
import asyncio
import os

# 加载环境变量
load_dotenv()

"""
.env文件中：
API_KEY="sk-xxxx"
DEEPSEEK_API_KEY="XXXXXXXXXXXXXXX"
"""

class MCPSSEClient:
    def __init__(self):
        """初始化 MCP sse HTTP 客户端"""
        self.exit_stack = AsyncExitStack() #异步开启关闭栈上下文管理器
        # 通过环境变量 LLM_PROVIDER 选择驱动模型,取值:qwen(默认) 或 deepseek
        # 选 qwen     -> 只需配置 API_KEY(阿里云 DashScope)
        # 选 deepseek -> 只需配置 DEEPSEEK_API_KEY(DeepSeek 官网)
        self.llm_provider = os.getenv("LLM_PROVIDER", "qwen").lower()
        if self.llm_provider == "deepseek":
            self.api_key = os.getenv("DEEPSEEK_API_KEY")
            self.base_url = "https://api.deepseek.com"
            self.model = "deepseek-chat"
        else:  # 默认 qwen
            self.api_key = os.getenv("API_KEY")  # 读取 通义千问 API Key
            self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            self.model = "qwen3.7-plus"
        if not self.api_key:
            raise ValueError(
                f"未找到 API KEY。当前 LLM_PROVIDER={self.llm_provider}，"
                f"请在 .env 中配置对应的 {'DEEPSEEK_API_KEY' if self.llm_provider == 'deepseek' else 'API_KEY'}"
            )
        print(f"[LLM配置] provider={self.llm_provider}, model={self.model}, base_url={self.base_url}")

        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        self.sessions = {}  # 存储多个服务端会话
        self.tools_map = {}  # 工具映射：工具名称 -> (MCP服务端 ID, 端点URL)
    #连接一个mcp的方法
    async def connect_to_server(self, server_id: str, endpoint_url: str):
        """
        连接到 MCP SSE HTTP 服务器
        :param server_id: 服务端标识符
        :param endpoint_url: 服务端端点URL
        """
        if server_id in self.sessions:
            raise ValueError(f"服务端 {server_id} 已经连接")

        # 连接到sse服务器，根据实际协议需要进行改造
        sse_transport = await self.exit_stack.enter_async_context(
            sse_client(endpoint_url)) #,sse_read_timeout=100,timeout=120
        print("sse_transport:",sse_transport)
        read_stream, write_stream = sse_transport #, _ 注意sse返回只有read_steam和write_stream
        # 创建会话
        session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream))
        print("session:",session)
        await session.initialize()
        self.sessions[server_id] = {
            "session": session,
            "read_stream": read_stream,
            "write_stream": write_stream,
            "endpoint_url": endpoint_url
        }
        print(f"已连接到 MCP sse 服务器: {server_id}")
        print("self.sessions:",self.sessions)
        # 更新工具映射
        response = await session.list_tools()
        print("response:",response)
        for tool in response.tools:
            self.tools_map[tool.name] = (server_id, endpoint_url)
    async def list_tools(self):
        """列出所有服务端的工具"""
        if not self.sessions:
            print("没有已连接的服务端")
            return
        print("已连接的服务端工具列表:")
        for tool_name, (server_id, _) in self.tools_map.items():
            print(f"工具: {tool_name}, 来源服务端: {server_id}")
    async def process_query(self, messages: list) -> str:
        """
        处理用户查询，支持多次工具调用
        :param messages: 消息历史列表
        :return: 最终响应内容
        """
        results = []

        # 构建统一的工具列表
        available_tools = []
        for tool_name, (server_id, _) in self.tools_map.items():
            session = self.sessions[server_id]["session"]
            response = await session.list_tools()
            for tool in response.tools:
                # if tool.name == tool_name:
                    # 确保函数名符合规范（替换连字符为下划线）
                    # safe_name = tool.name.replace('-', '_')
                    #functioncalling的结构
                available_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.inputSchema
                    }
                })
        print('整合的服务端工具列表:', available_tools)

        # 循环处理工具调用
        while True:
            # 请求模型处理
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=available_tools,
                tool_choice="auto",
                max_tokens=8192,
                temperature=0,
                stream=False,
                timeout=20,
                parallel_tool_calls=True,  # 通义千问特有的控制，支持多工具调用打开默认False
            )
            print("模型响应:", response)
            # 检查是否需要工具调用
            if response.choices[0].finish_reason == "tool_calls":
                tool_calls = response.choices[0].message.tool_calls #触发的工具list
                print("工具调用请求:", tool_calls)
                # 一回合对话有可能调用多个工具，因此需要解析并执行所有的工具调用
                for tool_call in tool_calls:
                    # 恢复原始工具名（将下划线转换回连字符）
                    original_tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments) #json（str）->参数字典
                    print("tool_args:",tool_args)
                    # 根据工具名称找到对应的服务端
                    server_info = self.tools_map.get(original_tool_name)
                    if not server_info:
                        raise ValueError(f"未找到工具 {original_tool_name} 对应的服务端")
                    server_id, _ = server_info
                    session = self.sessions[server_id]["session"]
                    print(f"\n调用工具 {original_tool_name} (服务端: {server_id}) 参数: {tool_args}\n")
                    #call_tool方法实现了client向server传递参数{tool_args},让MCP server执行对应工具返回结果tool_result
                    tool_result = await session.call_tool(original_tool_name, tool_args)
                    print("MCP工具调用返回结果tool_result:", tool_result)
                    # 将工具调用结果添加到消息历史中
                    results.append(tool_result.content[0].text)
                messages=([{"role": "user", "content": f"原始问题：{messages}\n工具结果：{json.dumps(results)}"}]) #将用户问题和工具得到的答案拼接在一起组成上下文
            else:
                # 如果没有工具调用，返回最终响应
                return response.choices[0].message.content

    async def chat_loop(self):
        """运行交互式聊天循环"""
        print("MCP sse  客户端已启动！输入 'exit' 退出")
        while True:
            try:
                query = input("问: ").strip()
                if query.lower() == 'exit':
                    break
                response = await self.process_query([{"role": "user", "content": query}])
                print(f"AI回复: {response}")
            except Exception as e:
                print(f"发生错误: {str(e)}")
    async def clean(self):
        """清理所有资源"""
        await self.exit_stack.aclose()
        self.sessions.clear()
        self.tools_map.clear()


server_url=os.getenv("server_url")
#定义工具名和工具函数之间的对应关系
async def main():
    # 启动并初始化 MCP 客户端
    client = MCPSSEClient()
    try:
        # 连接多个 MCP Streamable HTTP 服务器
        await client.connect_to_server(
            "stock_server",
            f"http://{server_url}:7336/sse"
        )
        await client.connect_to_server(
            "turn_human_server",
            f"http://{server_url}:7335/sse"
        )
        await client.connect_to_server(
            "policy_reply_server",
            f"http://{server_url}:7337/sse"
        )
        # 列出可用工具,注意list_tools是打印展示client绑定的工具，而非从3个MCP server这里获取tools
        await client.list_tools()
        # 运行交互式聊天循环
        await client.chat_loop()
    finally:
        # 清理资源
        await client.clean()
if __name__ == "__main__":
    asyncio.run(main())

#%%
#我想了解一下中国银行的股市情况
#哎，中国石油又跌了
#你好
#爽死了，上证指数
#我想死，妈的，中国银行又跌了
#深能源A这个股票亏的好惨啊
#中国石油和中国银行涨疯了，开心

