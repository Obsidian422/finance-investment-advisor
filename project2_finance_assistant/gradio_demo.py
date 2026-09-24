"""
本文件用于搭建一个简易的可以传递历史记录的智能对话前端页面
pip install gradio
"""
import os
import gradio as gr
import asyncio
from typing import AsyncGenerator, List, Tuple
from multi_user_finance_assistant_main_with_session import *
# 当前会话ID,首次调用后由后端返回并保持,实现多轮持续对话
_current_session_id = ""
#接受gradio前端传递的信息->进行消息转换,调用后端消息服务处理,完成消息处理后流式输出
async def gradio_wrapper(message: str, chat_history : List[List[str]]) -> AsyncGenerator[str, None]:
    global _current_session_id
    # 调用你的对话函数
    print("message:",message)
    response=await chat_service(current_message=message, session_id=_current_session_id)
    _current_session_id = response.get("session_id", _current_session_id)
    print("response:",response)
    return response.get("response","程序出现错误")

# 创建聊天界面
demo = gr.ChatInterface(
    fn=gradio_wrapper,
    title="金融投资虚拟顾问小e",
    description="我是您的智能助理,我能预测股价、解答您的金融问题、审查金融文章风险、转人工服务等",
    chatbot=gr.Chatbot(
        height=500
    ),
    textbox=gr.Textbox(
        placeholder="请输入您的问题...",
        container=False,
        scale=7,
        autofocus=True
    ),
)
# 启动应用
if __name__ == "__main__":
    # 初始化服务器;share 默认关闭(开启会生成公网穿透链接),如需外网访问:GRADIO_SHARE=1 python gradio_demo.py
    demo.launch(
        server_name="0.0.0.0",  # 允许其他主机访问
        server_port=9996,
        share=os.getenv("GRADIO_SHARE", "0") == "1",
    )