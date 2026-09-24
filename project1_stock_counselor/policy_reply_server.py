"""
政策回复MCP
"""

from typing import Any
from mcp.server.fastmcp import FastMCP
from function_utils import *
mcp = FastMCP("policy_reply_server", host="0.0.0.0", port=7337) #修改mcp服务端口
#定义基于用户情绪与近三天的涨跌决定话术回复策略
async def message_by_chat_policy(emotion,three_day_trend,future_trend=None):
    """
    :param emotion:
    :param three_day_trend:
    :param future_trend:
    :return:
    """
    if emotion=="高兴" and '上涨' in three_day_trend:
        return_message=f"另外，{three_day_trend}\n真为您感到高兴~"
    elif emotion=="高兴" and '下跌' in three_day_trend:
        return_message=f"另外，{three_day_trend}\n请问您为什么那么高兴呢？"
    elif emotion=="悲伤" and '下跌' in three_day_trend and '上涨' in future_trend:
        return_message = f"另外，{three_day_trend}\n但是经过我们的预测，{future_trend}"
    elif emotion == "悲伤" and '下跌' in three_day_trend and '下跌' in future_trend:
        return_message = f"另外，{three_day_trend}\n经过我们的预测，{future_trend}\n希望您能谨慎投资呢~"
    elif emotion == "悲伤" and '上涨' in three_day_trend:
        return_message = f"另外，{three_day_trend}\n这是好事情呀，请问您为什么难过呢？"
    else:
        return_message=f"我无法获取到您提到的股票信息，请您放平心态，理性投资~"
    return return_message




#工具1:话术策略回复MCP
@mcp.tool()
async def message_by_chat_policy_tool(emotion :str, three_day_trend : str, future_trend=None) -> str:
    """
    基于用户表达的'高兴'、'悲伤'的情绪及历史三天的涨跌趋势、以及未来的趋势分析结果，策略性回复用户
    :param emotion:用户的情绪，值必须从['高兴','悲伤']中根据用户实际情况进行选取
    :param three_day_trend:近三天股票趋势描述，如：近三天有上涨的趋势，近三天有下跌的趋势，没有查询到X股票的收盘价数据
    :param future_trend:未来股票趋势描述，没有查询到X股票的收盘价数据
    :return:回复用户的话术
    """
    return_message =await message_by_chat_policy(emotion, three_day_trend,future_trend)
    return return_message


if __name__ == "__main__":
    # 以标准 I/O 方式运行 MCP 服务器
    mcp.run(transport='sse')

    #nohup python policy_reply_server.py &