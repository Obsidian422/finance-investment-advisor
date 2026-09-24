"""
股价MCP：包含未来股价预测工具、近期股价查询工具
"""

import os
from typing import Any
from mcp.server.fastmcp import FastMCP
from function_utils import exponential_moving_average
#近三日股票服务器的代码实现
import pandas as pd
import asyncio
import numpy as np

# 当前文件所在目录,数据文件与本文件同目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STOCK_DATA_PATH = os.path.join(BASE_DIR, 'stock_data.xlsx')

# 初始化 MCP 服务器
mcp = FastMCP("stock_server", host="0.0.0.0", port=7336) #修改mcp服务端口
#查询近三天股价移动平均值，并与再早之前一周的平均值进行比较查看近三天股价涨跌情况
async def cal_close_price_trend(stock_name):
    if stock_name=="上证指数":
        stock_data = pd.read_excel(
            STOCK_DATA_PATH,
            parse_dates=['Date'], sheet_name='上证指数')
    elif stock_name=="中国石油":
        stock_data = pd.read_excel(STOCK_DATA_PATH,parse_dates=['Date'], sheet_name='中国石油')
    elif stock_name=="中国银行":
        stock_data = pd.read_excel(STOCK_DATA_PATH,parse_dates=['Date'], sheet_name='中国银行')
    else:
        return f"没有查询到{stock_name}股票的收盘价数据"

    last_three_days_stock_price=list(stock_data['Close'][-3:])
    print("last_three_days_stock_price:",last_three_days_stock_price)
    last_three_days_avg_price=round(np.average(last_three_days_stock_price),3)
    print("last_three_days_avg_price:",last_three_days_avg_price)
    #计算历史一周的收盘价数据
    last_weeks_stock_price=list(stock_data['Close'])[-7:-3]
    last_week_avg_price=round(np.average(last_weeks_stock_price),3)
    print("last_week_avg_price:",last_week_avg_price)
    if last_three_days_avg_price>=last_week_avg_price:
        trend="上涨"
    else:
        trend="下跌"
    await asyncio.sleep(0.1)
    return f"查询到股票:{stock_name},近三天的平均收盘价为:{last_three_days_avg_price},之前一周的平均收盘价为：{last_week_avg_price},近三天有{trend}的趋势"

# result=cal_close_price_trend(stock_name="上证指数")
# print(result)
#%%
#函数2：定义预测未来7天股票收盘价及与近三天收盘价进行比较涨跌的函数
async def predict_future_7data(stock_name):
    if stock_name=="上证指数":
        stock_data = pd.read_excel(
            STOCK_DATA_PATH,
            parse_dates=['Date'], sheet_name='上证指数')
    elif stock_name=="中国石油":
        stock_data = pd.read_excel(
            STOCK_DATA_PATH,
            parse_dates=['Date'], sheet_name='中国石油')
    elif stock_name=="中国银行":
        stock_data = pd.read_excel(
            STOCK_DATA_PATH,
            parse_dates=['Date'], sheet_name='中国银行')
    else:
        return f"我无法预测未来7日{stock_name}股票的收盘价"
    stock_data.asfreq('D')
    series = pd.Series(np.float16(stock_data['Close']), index=stock_data['Date'])
    # 计算EMA并预测未来10期
    alpha = 0.8  # 平滑因子
    forecast =exponential_moving_average(series, alpha, forecast_periods=3)
    print("forecast:",forecast)
    forecast_in_oneline=",".join([str(round(k,3)) for k in list(forecast)[-7:]])
    print("forecast_in_oneline:",forecast_in_oneline)
    #计算未来七天的均值
    avg_value=round(np.average(np.array(forecast).tolist()[-7:]),3)
    #计算股票近三天的平均收盘价
    avg_last_three_days_stock_price = stock_data['Close'][-3:].mean()

    print("last_three_days_stock_price:", avg_last_three_days_stock_price,"avg_value:",avg_value)
    if avg_last_three_days_stock_price>=avg_value:
        return_message = f"未来7天{stock_name}股票的收盘价预测结果为:{forecast_in_oneline}，未来7天平均收盘价为{avg_value}，预计会比近期价格有所下跌" #近三天股票{stock_name}的平均收盘价为{last_three_days_stock_price}，
    else:
        return_message = f"未来7天{stock_name}股票的收盘价预测结果为:{forecast_in_oneline}，未来7天平均收盘价为{avg_value}，预计会比近期价格有所上涨" #近三天股票{stock_name}的平均收盘价为{last_three_days_stock_price}，
    await asyncio.sleep(0.1)
    return return_message

# async def main():
#     return_message=await predict_future_7data(stock_name="上证指数")
#     print(return_message)
# asyncio.run(main())
# 未来7天上证指数股票的收盘价预测结果为:81.761,80.052,75.01,77.102,77.102,77.102,77.102，未来7天平均收盘价为77.89，预计会比近期价格有所上涨
#%%
#工具1:近三天股票涨跌计算
@mcp.tool()
async def predict_future_7data_tool(stock_name :str) -> str:
    """
    输入指定的股票名称，返回股票未来的涨跌趋势
    :param stock_name:股票名称，如：上证指数,中国石油,中国银行等
    :return: 股票未来的涨跌趋势描述，如：未来七天将上涨/下跌
    """
    return_message = await predict_future_7data(stock_name)
    return return_message


#工具2：计算近三天股票趋势
@mcp.tool()
async def cal_close_price_trend_tool(stock_name):
    """
    输入指定的股票名称，计算其近三日成交价
    :param stock_name:股票名称，如：上证指数,中国石油,中国银行等
    :return:近三天描述上涨/下跌的话术
    """
    return_message=await cal_close_price_trend(stock_name)
    return return_message




if __name__ == "__main__":
    # 以标准 I/O 方式运行 MCP 服务器
    mcp.run(transport='sse')


    #nohup python stock_sever.py &
