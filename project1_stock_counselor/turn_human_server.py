"""
pip install mcp
"""
from typing import Any
from mcp.server.fastmcp import FastMCP
from function_utils import *
#转人工MCP服务器的代码实现

# 初始化 MCP 服务器
mcp = FastMCP("turn_human_server", host="0.0.0.0", port=7335) #修改mcp服务端口
#定义转人工函数,attitude态度
async def turn_human(attitude):
    if attitude == "自杀倾向":
        return_message="冷静，一定要冷静，现在立马为您升级人工服务~"
    else:
        return_message="" #如果不想自杀，啥都不返回
    #真实业务中需要调用内部系统的转人工API来实现人工客服的转接
    return return_message


#工具1:转人工工具
@mcp.tool()
async def turn_human_tool(attitude :str,event: str) -> str:
    """
     识别有自杀倾向的用户，转到人工进行干预劝导
    :param attitude: 自杀倾向，在有['自杀倾向','无自杀倾向']中选择值
    :return: 转人工成功的引导语言
    """
    return_message = await turn_human(attitude)
    print("return_message:", return_message)
    return return_message



if __name__ == "__main__":
    # 以标准 I/O 方式运行 MCP 服务器
    mcp.run(transport='sse') #"stdio", "sse", "streamable-http"

    #nohup python turn_human_server.py &


