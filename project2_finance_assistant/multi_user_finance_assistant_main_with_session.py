"""
多用户多MCP多智能体协同主程序，使用全局字典管理会话状态
修复版本：确保connection_status正确初始化
"""
from dotenv import load_dotenv
import os
import traceback
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel, Agent, Runner, set_default_openai_client
from agents.model_settings import ModelSettings
from agents import set_tracing_disabled
from agents.mcp import MCPServerSse
import asyncio
import uuid
from typing import Dict, List, Any
from agents import (Agent, HandoffOutputItem, ItemHelpers, MessageOutputItem,
                    ToolCallItem, ToolCallOutputItem)
from function_handler import LLM_PROVIDER, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

# 全局配置
set_tracing_disabled(True)
# 统一从项目根目录(上一级)加载 .env,整个工程只需维护一份配置
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
server_url = os.getenv("server_url")
# 全局智能体模型(由 LLM_PROVIDER 决定使用 qwen 或 deepseek)
deepseek_model = None
# 全局会话存储
global_sessions: Dict[str, Dict[str, Any]] = {}
#{session_id: {"messages": List, "current_agent": Agent,"user_id":"user1"}}
class MCPManager:
    """管理所有MCP服务器的连接"""
    def __init__(self):
        self.servers = {}
        self.connection_status = {}  # 初始化连接状态字典
    async def initialize(self):
        """初始化所有MCP服务器"""
        self.servers = {
            "finance_consult": MCPServerSse(
                params={"url": f"http://{server_url}:9339/sse"},
                cache_tools_list=True,
                client_session_timeout_seconds=200
            ),
            "article_check": MCPServerSse(
                params={"url": f"http://{server_url}:9330/sse"},
                cache_tools_list=True,
                client_session_timeout_seconds=200
            ),
            "investment": MCPServerSse(
                params={"url": f"http://{server_url}:8336/sse"},
                cache_tools_list=True,
                client_session_timeout_seconds=200
            ),
            "turn_human": MCPServerSse(
                params={"url": f"http://{server_url}:8335/sse"},
                cache_tools_list=True,
                client_session_timeout_seconds=200
            )
        }

        # 连接所有服务器并初始化状态
        for name, server in self.servers.items():
            try:
                await server.connect()
                self.connection_status[name] = True
            except Exception as e:
                print(f"连接MCP服务器 {name} 失败: {str(e)}")
                self.connection_status[name] = False

    def get_server(self, name: str):
        """获取指定的MCP服务器"""
        return self.servers.get(name)

    async def check_connections(self):
        """检查服务器连接状态，必要时重新连接"""
        for name, server in self.servers.items():
            try:
                # 尝试简单操作来检测连接状态
                if hasattr(server, 'tools_list'):
                    _ = server.tools_list  # 尝试访问属性来检测连接
                self.connection_status[name] = True
            except Exception as e:
                print(f"检测到MCP服务器 {name} 连接异常: {str(e)}，尝试重新连接...")
                self.connection_status[name] = False
                try:
                    await server.connect()
                    self.connection_status[name] = True
                    print(f"MCP服务器 {name} 重新连接成功")
                except Exception as e:
                    print(f"MCP服务器 {name} 重新连接失败: {str(e)}")
                    self.connection_status[name] = False

    async def close(self):
        """关闭所有连接"""
        for name, server in self.servers.items():
            try:
                await server.close()
                self.connection_status[name] = False
            except Exception as e:
                print(f"关闭MCP服务器 {name} 时出错: {str(e)}")

    def is_connected(self, server_name: str) -> bool:
        """检查指定服务器是否连接"""
        return self.connection_status.get(server_name, False)


class FinancialAssistant:
    def __init__(self):
        self.mcp_manager = MCPManager()
        self.initial_agent = None
        self.is_initialized = False
        # asyncio.Lock() 确保初始化代码只执行一次，即使多个协程同时调用 initialize()
        self.initialization_lock = asyncio.Lock()

    async def initialize(self):
        """初始化服务"""
        async with self.initialization_lock:
            if self.is_initialized:
                return

            global deepseek_model

            # 初始化智能体驱动模型(由 LLM_PROVIDER 决定 qwen / deepseek)
            external_client = AsyncOpenAI(
                base_url=LLM_BASE_URL,
                api_key=LLM_API_KEY
            )
            set_default_openai_client(external_client)
            deepseek_model = OpenAIChatCompletionsModel(
                model=LLM_MODEL,
                openai_client=external_client
            )

            # 初始化MCP服务器
            await self.mcp_manager.initialize()

            # 检查关键服务器连接状态
            critical_servers = ["finance_consult", "article_check", "investment", "turn_human"]
            for server in critical_servers:
                if not self.mcp_manager.is_connected(server):
                    raise ConnectionError(f"关键MCP服务器 {server} 连接失败")

            # 初始化智能体
            self.initial_agent = await self._initialize_agents()
            self.is_initialized = True

    async def _initialize_agents(self) -> Agent:
        """初始化所有智能体并返回初始智能体"""
        # 获取MCP服务器实例
        finance_consult_mcp_server = self.mcp_manager.get_server("finance_consult")
        article_check_mcp_server = self.mcp_manager.get_server("article_check")
        investment_mcp_server = self.mcp_manager.get_server("investment")
        turn_human_mcp_server = self.mcp_manager.get_server("turn_human")

        # 系统提示信息
        system_message_prompt = """你是一名热情而又有礼貌的金融AI助理
                只有在确认客户没有进一步问题，代表该项业务已完成，需要移交回'Switch Agent'智能体。
                注意：1、必须按照流程指引逐步完成任务
                2、如果用户要求转到人工客服，则需要根据当前智能体所在场景，调用'turn_human Agent'智能体。
                3、如果用户提供的信息不足，请向其询问以便于完成当前业务"""

        # 转人工智能体
        turn_human_agent_prompt = """1.调用turn_human_tool mcp工具完成转到人工客服的操作"""
        turn_human_agent = Agent(
            name="turn_human Agent",
            instructions="根据不同业务场景，转到相应的人工客服。" + turn_human_agent_prompt,
            handoff_description="当用户要求转人工时，调用该智能体回复",
            model_settings=ModelSettings(tool_choice="auto"),
            model=deepseek_model,
            mcp_servers=[turn_human_mcp_server]
        )

        # 投资建议智能体
        investment_agent_prompt = """1.询问用户需要预测或查询的股票名称，若已经有股票名称则根据条件进行子步骤
                1a) 如果用户想要对未来股票走势进行预测，请调用'predict_future_7data_tool'函数
                1b) 如果用户想要对当前股票收盘价进行查询，请调用'cal_close_price_trend_tool'函数
                1c) 如果用户想要生成股票投资预测报告，请继续下一步
                2.如果用户希望生成股票投资预测报告
                2a) 先调用'predict_future_7data_tool'函数
                2b) 接着调用'cal_close_price_trend_tool'函数
                2c) 最后调用'generation_stock_prediction_report_tool'函数
                3. 确认用户是否有问题，如果用户没有其它问题，调用移交回'Switch Agent'智能体"""
        investment_agent = Agent(
            name="Investment Agent",
            instructions=system_message_prompt + investment_agent_prompt,
            handoff_description="当用户咨询股票未来趋势、查询当前股价或希望生成股票投资报告时，调用该智能体回复",
            model_settings=ModelSettings(tool_choice="auto"),
            model=deepseek_model,
            mcp_servers=[investment_mcp_server]
        )

        # 金融文章质检智能体
        article_check_agent_prompt = """1.获取用户需要审查风险的金融文章文本。
                1a) 如果用户想要对文章进行专业性审查，请调用'professional_check_tool'函数。
                1b) 如果用户想要对文章进行规范性审查，请调用'basic_check_tool'函数。
                1c) 如果用户想要生成审查分析报告，请跳到第 2 步
                1d) 如果用户想要对原文档进行高质量修改，请跳到第 3 步
                2.如果用户希望生成审查分析报告
                2a) 调用'professional_check_tool'函数
                2b) 调用'basic_check_tool'函数
                2c) 调用'produce_check_result_report_tool'函数
                3.如果用户要对原文档进行高质量修改
                3a) 调用'professional_check_tool'函数
                3b) 调用'basic_check_tool'函数
                3c) 调用'produce_refine_report_tool'函数
                4. 确认用户是否有问题，如果用户没有其它问题，调用移交回'Switch Agent'智能体"""
        article_check_agent = Agent(
            name="Article Check Agent",
            instructions=system_message_prompt + article_check_agent_prompt,
            handoff_description="当用户希望审查文章风险，修改文章或生成审查意见报告，调用该智能体进行回答",
            model_settings=ModelSettings(tool_choice="auto"),
            model=deepseek_model,
            mcp_servers=[article_check_mcp_server]
        )

        # 金融智能咨询智能体
        consult_agent_prompt = """1.获取用户需要询问的问题
                2.如果用户希望查询本地知识库，请调用'invest_policy_consult_tool'函数
                3.如果用户希望网络检索问题，请调用'finance_news_search_consult_tool'函数
                4.如果用户仅表达希望得到某问题的答案
                4a) 先调用'invest_policy_consult_tool'函数
                4a1) 若检索到本地知识库答案则直接进行回复
                4a2) 若未检索到本地知识库答案则跳到第 5 步
                5.调用'finance_news_search_consult_tool'函数
                6. 确认用户是否有问题，如果用户没有其它问题，调用移交回'Switch Agent'智能体"""
        consult_agent = Agent(
            name="Consult Agent",
            instructions=system_message_prompt + consult_agent_prompt,
            handoff_description="当用户咨询问题时，调用该智能体进行回答",
            model=deepseek_model,
            mcp_servers=[finance_consult_mcp_server]
        )

        # 业务转接智能体
        switch_agent_prompt = """你是一名热情而又专业的业务转接助理,你能根据用户的意图转接到咨询问题、文章审核、股价查询或人工服务智能体"""
        switch_agent = Agent(
            name="Switch Agent",
            instructions=switch_agent_prompt + "请根据用户需求移交给合适的智能体进行回复，若没合适的则自己回答",
            handoffs=[investment_agent, turn_human_agent, article_check_agent, consult_agent],
            model=deepseek_model
        )

        # 设置智能体之间的互转关系
        consult_agent.handoffs.extend([turn_human_agent, switch_agent, article_check_agent, investment_agent])
        article_check_agent.handoffs.extend([turn_human_agent, switch_agent, consult_agent, investment_agent])
        investment_agent.handoffs.extend([turn_human_agent, switch_agent, consult_agent, article_check_agent])
        turn_human_agent.handoffs.extend([switch_agent, article_check_agent, investment_agent, consult_agent])

        return switch_agent  # 返回初始智能体

    async def create_session(self, user_id: str = "default_user") -> str:
        """创建新会话并返回session_id"""
        if not self.is_initialized:
            await self.initialize()

        session_id = str(uuid.uuid4())
        global_sessions[session_id] = {
            "user_id": user_id,
            "messages": [],
            "current_agent": self.initial_agent
        }
        return session_id

    async def process_message(self, session_id: str, message: str) -> str:
        """处理用户消息"""
        if not self.is_initialized:
            await self.initialize()
        # 检查并确保MCP服务器连接正常
        await self.mcp_manager.check_connections()
        session = global_sessions.get(session_id)
        print("session:",session)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # 添加用户消息到会话历史
        session["messages"].append({"content": message, "role": "user"})
        print("xxxx:",session)

        # 处理消息(传完整历史,避免切片截断破坏 tool_call 上下文)
        try:
            result = await Runner.run(
                starting_agent=self.initial_agent if session.get("current_agent")==None else session["current_agent"],
                input=session["messages"]
            )
        except Exception as run_err:
            print(f"Runner.run() 异常: {run_err}")
            traceback.print_exc()
            raise

        # 处理结果
        response = ""
        for new_item in result.new_items:
            agent_name = new_item.agent.name if hasattr(new_item, 'agent') else "未知智能体"
            if isinstance(new_item, MessageOutputItem):
                response += f"{agent_name}: {ItemHelpers.text_message_output(new_item)}\n"
            elif isinstance(new_item, HandoffOutputItem):
                response += f"已从{new_item.source_agent.name}转接到{new_item.target_agent.name}\n"
                session["current_agent"] = new_item.target_agent  # 更新当前智能体
            elif isinstance(new_item, ToolCallItem):
                response += f"{agent_name}: 调用工具: {new_item.raw_item.name}\n"
            elif isinstance(new_item, ToolCallOutputItem):
                # output 可能是任意类型,安全转字符串后截断
                try:
                    out_str = str(new_item.output)[:100]
                except Exception:
                    out_str = "(无法显示)"
                response += f"{agent_name}: 工具调用结果: {out_str}...\n"

        # 更新对话历史
        session["messages"] = result.to_input_list()
        return result.final_output

    async def close_session(self, session_id: str):
        """关闭会话"""
        if session_id in global_sessions:
            del global_sessions[session_id]

    async def shutdown(self):
        """关闭服务"""
        await self.mcp_manager.close()
        self.is_initialized = False


# 全局单例助手实例
_assistant_instance = None
_assistant_lock = asyncio.Lock()


async def get_assistant():
    """获取或创建助手单例"""
    global _assistant_instance
    async with _assistant_lock:
        if _assistant_instance is None:
            _assistant_instance = FinancialAssistant()
            await _assistant_instance.initialize()
        return _assistant_instance


async def chat_service(current_message: str, session_id: str = "") -> dict:
    """
    处理用户消息的入口函数
    :param current_message: 用户消息内容
    :param session_id: 会话ID，如果为空则创建新会话
    :return: 包含响应和会话ID的字典
    """
    try:
        assistant = await get_assistant()
        print("assistant:",assistant)
        if not session_id or session_id not in global_sessions:
            # 创建新会话
            session_id = await assistant.create_session()
            print(f"Created new session: {session_id}")

        response = await assistant.process_message(session_id, current_message)
        print("response1:",response)
        return {
            "session_id": session_id,
            "response": response,
            "status": "success"
        }
    except Exception as e:
        tb = traceback.format_exc()
        print(f"chat_service 异常:\n{tb}")
        return {
            "session_id": session_id,
            "response": f"处理消息时出错: {str(e)}\n\n详细错误:\n{tb}",
            "status": "error"
        }


async def cleanup():
    """清理资源"""
    global _assistant_instance
    async with _assistant_lock:
        if _assistant_instance is not None:
            await _assistant_instance.shutdown()
            _assistant_instance = None
            global_sessions.clear()


