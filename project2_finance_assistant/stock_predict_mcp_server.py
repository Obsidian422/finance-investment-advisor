"""
股票信息预测MCP
"""
import os
import sys
from pathlib import Path
# 确保能 import 同目录下的 function_handler
sys.path.append(str(Path(__file__).resolve().parent))
from typing import Any
from mcp.server.fastmcp import FastMCP
from function_handler import exponential_moving_average,LLM_replay
#近三日股票服务器的代码实现
import pandas as pd
import asyncio
import numpy as np

# project1 数据文件目录(与本文件所在目录同级)
BASE_DIR = Path(__file__).resolve().parent
PROJECT1_DIR = BASE_DIR.parent / "project1_stock_counselor"
STOCK_DATA_PATH = str(PROJECT1_DIR / "stock_data.xlsx")

# 初始化 MCP 服务器
mcp = FastMCP("stock_server", host="0.0.0.0", port=8336) #修改mcp服务端口
#查询收盘价近期表现
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
    str_last_weeks_stock_price=",".join([str(round(k,3)) for k in last_three_days_stock_price])
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
    return f"查询到股票:{stock_name},近三天收盘价为:{str(str_last_weeks_stock_price)},近三天的平均收盘价为:{last_three_days_avg_price},之前一周的平均收盘价为：{last_week_avg_price},近三天有{trend}的趋势"

# result=cal_close_price_trend(stock_name="上证指数")
# print(result)
#%%
#函数1：定义预测未来7天股票收盘价及与近三天收盘价进行比较涨跌的函数
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

#%%
#根据预测结果与当前结果,生成股票投资建议书
async def generation_stock_prediction_report(stock_name,current_stock_trend,future_7data_trend):
    prompt=f"""你是一个股票投资建议大师，你能根据股票{stock_name}查询到的结果：如当前的收盘价、最近7天的股票收盘价预测结果、历史7天的收盘价结果等，使用提供的生成大纲书写一份股票投资建议分析报告，必须要有数据分析过程及结论\n"""
    messages=f"""查询到的结果：
    当前及历史7天的收盘价数据：{current_stock_trend}
    未来7天收盘价预测数据：{future_7data_trend}
    生成大纲：
    标题：{stock_name}投资建议分析报告
    股票名称
    近期趋势
    未来趋势
    投资建议
    风险提示
    输出:"""
    print("messages:",messages)
    try:
        report_message=await LLM_replay(prompt_template=prompt, messages=messages)
        return_message=report_message.choices[0].message.content
    except:
        return_message="很抱歉，生成报告错误，但我依旧希望生成报告"
    return return_message
#%%
#工具1:近三天股票涨跌计算
@mcp.tool()
async def predict_future_7data_tool(stock_name :str) -> str:
    """
    输入指定的股票名称，预测股票未来的涨跌趋势数据
    :param stock_name:用户提到的股票名称。例如:上证指数,中国石油,中国银行等
    :return: 未来7天收盘价
    """
    return_message = await predict_future_7data(stock_name)
    return return_message
#工具2：计算近三天股票趋势
@mcp.tool()
async def cal_close_price_trend_tool(stock_name):
    """
    输入指定的股票名称，计算其近三日收盘价
    :param stock_name:股票名称。例如：上证指数,中国石油,中国银行等
    :return:近三天收盘价数据
    """
    return_message=await cal_close_price_trend(stock_name)
    return return_message
#工具3：生成投资建议报告
@mcp.tool()
async def generation_stock_prediction_report_tool(stock_name,current_stock_trend,future_7data_trend):
    """
    输入指定的股票名称，近期成交价、未来7日预测结果，生成投资建议报告
    :param stock_name:用户提到的股票名称。例如：上证指数,中国石油,中国银行等
    :param current_stock_trend:近三天收盘价
    :param future_7data_trend:未来7天收盘价
    :return:投资建议报告
    """
    return_message=await generation_stock_prediction_report(stock_name,current_stock_trend,future_7data_trend)
    return return_message



if __name__ == "__main__":
    # 以标准 sse方式运行 MCP 服务器
    mcp.run(transport='sse')
    #nohup python stock_predict_mcp_server.py &


#uv 来启动服务, uv add  conda activate  nohup uv run stock_predict_mcp_server.py &
