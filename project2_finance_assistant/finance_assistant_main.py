"""
金融咨询MCP
"""
# 导入必要的库和模块
from dotenv import load_dotenv
import os
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel, Agent, Runner, set_default_openai_client
from agents.model_settings import ModelSettings
from agents import set_tracing_disabled
import sys
from agents import function_tool
import numpy as np
import pandas as pd
import requests, json
from agents import trace
from agents.mcp import MCPServer, MCPServerSse, MCPServerStdio  # 添加MCPServerStdio
from contextlib import AsyncExitStack
import asyncio
import os
from function_handler import LLM_PROVIDER, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
# sys.path.append("./project2_finance_assistant")

# 设置系统路径并禁用跟踪
set_tracing_disabled(True)  # 是否跟踪智能体运行过程
# 加载环境变量并初始化智能体驱动模型(由 LLM_PROVIDER 决定 qwen / deepseek)
# 统一从项目根目录(上一级)加载 .env,整个工程只需维护一份配置
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
server_url=os.getenv("server_url")
external_client = AsyncOpenAI(
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY
)
# 取代默认的OpenAI模型为自定义的LLM client
set_default_openai_client(external_client)
deepseek_model = OpenAIChatCompletionsModel(
    model=LLM_MODEL,
    openai_client=external_client
)
print(f"智能体模型初始化完成: provider={LLM_PROVIDER}, model={LLM_MODEL}")
# %%
from agents import (Agent,HandoffOutputItem,ItemHelpers,MessageOutputItem,RunContextWrapper,
Runner,ToolCallItem,ToolCallOutputItem,TResponseInputItem,function_tool,handoff, trace)
# 初始化所有智能体并连接MCP服务器
async def run_all_agents():
    """初始化所有智能体并连接到对应的MCP服务器（改进版）"""
    print("开始初始化所有智能体并连接MCP服务器...")
    # # Initialize remote SSE MCP server (if needed)
    # MCPServerStdio(params={"command": "python",
    #       "args": [
    #         "-y",
    #         "@gitee/mcp-gitee@latest"
    #       ]},
    #                cache_tools_list=,
    #                name=
    #                client_session_timeout_seconds=)

    finance_consult_mcp_server = MCPServerSse(
        params={"url": f"http://{server_url}:9339/sse"},
        cache_tools_list=True,
        client_session_timeout_seconds=200
    )
    article_check_mcp_server=MCPServerSse(
        params={"url": f"http://{server_url}:9330/sse"},
        cache_tools_list=True,
        client_session_timeout_seconds=200 #the read timeout passed to the MCP ClientSession.
    )
    investment_mcp_server=MCPServerSse(
        params={"url": f"http://{server_url}:8336/sse"},
        cache_tools_list=True,
        client_session_timeout_seconds=200
    )
    turn_human_mcp_server=MCPServerSse(
        params={"url": f"http://{server_url}:8335/sse"},
        cache_tools_list=True,
        client_session_timeout_seconds=200
    )
    #在连接了上述这些MCP服务器的上下文中进行智能体定义与调用,这样Multi_agent系统是能关联上工具的
    async with finance_consult_mcp_server, article_check_mcp_server,investment_mcp_server,turn_human_mcp_server:
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
        3. 确认用户是否有问题，如果用户没有其它问题，则移交回'Switch Agent'智能体"""
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
        switch_agent_prompt = """你是一名热情而又专业的业务转接助理,你能根据用户的意图进行相应业务的转接。"""
        switch_agent = Agent(
            name="Switch Agent",
            instructions=switch_agent_prompt + "请根据用户需求移交给合适的智能体进行回复，若没合适的则自己回答",
            handoffs=[investment_agent, turn_human_agent, article_check_agent, consult_agent],
            model=deepseek_model
        )
        # 将上面的所有智能体之间都实现互转
        consult_agent.handoffs.extend([turn_human_agent,switch_agent,article_check_agent,investment_agent])
        article_check_agent.handoffs.extend([turn_human_agent,switch_agent,consult_agent,investment_agent])
        investment_agent.handoffs.extend([turn_human_agent,switch_agent,consult_agent,article_check_agent])
        #能回转到任何一个智能体
        turn_human_agent.handoffs.extend([switch_agent,article_check_agent,investment_agent,consult_agent])

        # 定义所有智能体及其对应的MCP服务器配置
        agent_configs = {
            "Switch Agent": {
                "agent": switch_agent,
                "servers": []
            },
            "turn_human Agent": {
                "agent": turn_human_agent,
                "servers": [ #mcp server
                    {"name": "turn_human_server",
                     "url": f"http://{server_url}:8335/sse",
                     "type": "sse",
                     "cache_tools_list": True,
                     "timeout": 200.0
                    }
                ]
            },
            "Investment Agent": {
                "agent": investment_agent,
                "servers": [
                    {
                        "name": "investment_mcp_server",
                        "url": f"http://{server_url}:8336/sse",
                        "type": "sse",
                        "cache_tools_list": True,
                        "timeout": 200.0
                    },
                ]
            },
            "Article Check Agent": {
                "agent": article_check_agent,
                "servers": [
                    {
                        "name": "article_check_mcp_server",
                        "url": f"http://{server_url}:9330/sse",
                        "type": "sse",
                        "cache_tools_list": True,
                        "timeout": 200.0
                    },
                ]
            },
            "Consult Agent": {
                "agent": consult_agent,
                "servers": [
                    {
                        "name": "finance_consult_mcp_server",
                        "url": f"http://{server_url}:9339/sse",
                        "type": "sse",
                        "cache_tools_list": True,
                        "timeout": 200.0
                    },
                ]
            }
        }
        print(agent_configs.get("Switch Agent").get("agent"))
        # 记录多轮消息的记忆
        messages = []
        #定义在gradio中传递的消息列表,其中只有消息没有MCP调用之类的消息
        delivery_message_list=[]
        current_agent = switch_agent  # 初始智能体为Switch Agent
        while True:
            current_message = input("请输入本轮消息：")
            # 新增功能：输入"查看工具"时显示当前智能体的MCP服务器工具
            if current_message.lower() in ["查看工具", "show tools"]:
                config = agent_configs.get(current_agent.name, {"servers": []})
                servers = config["servers"]
                if not servers:
                    print("当前智能体未连接任何MCP服务器")
                    continue
            if current_message.lower() in ["退出", "exit", "quit"]:
                print("服务结束")
                break

            # 构建用户消息
            messages.append({"content": current_message, "role": "user"})
            # delivery_message_list.append({"content": current_message, "role": "user"})
            # 处理用户请求并获取结果和新的智能体 #这里如果用messages作为历史记录传参需要全取,只取部分可能会报错因为functioncall需要有固定的消息传递格式
            result = await Runner.run(starting_agent=current_agent, input=messages)  #delivery_message_list[-8:]
            print("result:", result)
            delivery_message_list.append({"content": result.final_output, "role": "assistant"})
            # 处理结果输出
            for new_item in result.new_items:
                agent_name = new_item.agent.name if hasattr(new_item, 'agent') else "未知智能体"
                if isinstance(new_item, MessageOutputItem):
                    print(f"{agent_name}: {ItemHelpers.text_message_output(new_item)}")
                elif isinstance(new_item, HandoffOutputItem):
                    print(f"Handed off from {new_item.source_agent.name} to {new_item.target_agent.name}")
                    current_agent = new_item.target_agent  # 更新当前智能体
                elif isinstance(new_item, ToolCallItem):
                    print(f"{agent_name}:调用工具:{new_item.raw_item.name},传参:{new_item.raw_item.arguments}")
                elif isinstance(new_item, ToolCallOutputItem):
                    print(f"{agent_name}: 工具调用输出: {new_item.output}")
                else:
                    print(f"{agent_name}: Skipping item: {new_item.__class__.__name__}")
            # 更新对话历史
            messages = result.to_input_list()
            print(f"当前对话历史长度: {len(messages)}")
            print(f"当前处理智能体: {current_agent.name}")


# 主函数
async def main():
    # 初始化所有智能体
    await run_all_agents()


# 运行主函数
if __name__ == "__main__":
    asyncio.run(main())

# test1:单智能体多MCP-股价查询/预测-股票报告生成测试
# 我想咨询一下近期上证指数的收盘价
# 顺带预测一下未来的趋势
# 好的，生成报告吧
# 没有了，谢谢

# test2:单智能体多MCP-金融智能咨询测试
# 金融经济学有什么好看的书推荐
# 问一下货币战争是哪一年写的
# 好的，我还想知道非法或受到国际制裁的行业有哪些

# test3:单智能体多MCP-金融文章检查测试
# 专业性检查:从专业性角度出发，帮我检查一下这篇文章，《全球增长基金的表现与风险分析.docx》
# 规范性检查:从字词规范性角度出发，帮我检查一下这篇文章《全球增长基金的表现与风险分析.docx》 规范性审查也做一下
# 生成审查报告吧
# 审查报告能否改的简短一些

# test4:多场景转人工
# 转人工

#test5:多智能体多MCP测试
# 查询一下中国石油近期收盘价数据，然后写一篇金融评论。另外，我咨询一下中国石化的创始人是谁？需要出现在金融评论中
#我不满意，转人工服务
#转回业务转交智能体

# test6:多智能体多MCP测试
