"""
转人工MCP
"""
from typing import Any
from mcp.server.fastmcp import FastMCP
#转人工MCP服务器的代码实现

# 初始化 MCP 服务器
mcp = FastMCP("turn_human_server", host="0.0.0.0", port=8335) #修改mcp服务端口

#工具1:转人工工具
@mcp.tool()
async def turn_human_tool(task :str) -> str:
    """
    识别用户有'转人工'的需求时，根据转人工的业务不同转到合适的人工客服
    :param task: 转人工业务，在['金融咨询','股票预测','文章审查','通用业务']中选择值
    :return: 转人工成功的引导语言
    """
    if task=="金融咨询":
        return_message ="您的业务已升级，下面将有咨询客服为您服务"
    elif task=="股票预测":
        return_message ="您的业务已升级，下面将由股票测算师为您服务"
    elif task=="文章审查":
        return_message ="您的业务已升级，下面将由风控专员为您服务"
    else: #通用业务
        return_message="您的业务已升级，下面将由人工坐席001号客服为您服务"
    print("return_message:", return_message)
    return return_message


# # 任务结束确认工具,弃用
# @mcp.tool()
# async def task_solved():
#     """
#     当前问题已处理完成，用户无额外问题时，调用该函数结束任务/
#     :return: 结束任务话术
#     """
#
#     return "问题已解决。无更多问题。"



if __name__ == "__main__":
    # 以标准 I/O 方式运行 MCP 服务器
    mcp.run(transport='sse')

    #nohup python turn_human_server.py &
