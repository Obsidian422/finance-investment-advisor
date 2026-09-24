#%%
"""
本文件用于使用指数时间序列预测算法来对未来7天的股票走势进行预测,后续MCP构建时将引用该函数
pip install statsmodels
pip install mcp
"""
import os
import pandas as pd
import numpy as np
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.arima.model import ARIMA
# from matplotlib import pyplot as plt

# 当前文件所在目录,数据文件与本文件同目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STOCK_DATA_PATH = os.path.join(BASE_DIR, 'stock_data.xlsx')

#%%
def simple_moving_average(series, window):
    """计算简单移动平均"""
    return series.rolling(window=window).mean()

#%%
import numpy as np
import pandas as pd
def exponential_moving_average(series, alpha, forecast_periods=1):
    """
    计算指数移动平均并预测未来值
    参数:
    series: pandas.Series，原始时间序列数据
    alpha: float，平滑因子，范围(0,1]
    forecast_periods: int，预测未来的期数，默认为1

    返回:
    forecast: pandas.Series，包含原始数据的EMA和平滑后的预测值
    """
    # 计算EMA
    ema = series.ewm(alpha=alpha, adjust=False).mean()
    # 获取最后一个EMA值作为预测基础
    last_ema = ema.iloc[-1]
    # 创建未来日期索引
    future_dates = pd.date_range(
        start=series.index[-1],
        periods=forecast_periods + 1,
        freq=pd.infer_freq(series.index)
    )[1:]
    # 创建预测值序列
    forecast_values = np.full(forecast_periods, last_ema)
    forecast_series = pd.Series(forecast_values, index=future_dates)
    # 合并原始数据的EMA和预测值
    full_forecast = pd.concat([ema, forecast_series])
    return full_forecast

#函数1：定义预测未来7天股票收盘价及与近三天收盘价进行比较涨跌的函数
def predict_future_7data(stock_name):
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
    return return_message

# input_data_list=np.float16(stock_data['Close'])
# index_date=stock_data['Date']
#%%
# 函数2：定义计算近三天收盘价与历史7天收盘价涨跌的函数
def cal_close_price_trend(stock_name):
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
    return f"查询到股票:{stock_name},近三天的平均收盘价为:{last_three_days_avg_price},之前一周的平均收盘价为：{last_week_avg_price},近三天有{trend}的趋势"

# return_message=cal_close_price_trend(stock_name="上证指数")
# print(return_message)
#%%
#定义基于用户情绪与近三天的涨跌决策
def message_by_chat_policy(emotion,three_day_trend,future_trend=None):
    """
    :param emotion:
    :param three_day_trend:
    :param future_trend:
    :return:
    """
    if emotion=="高兴" and '上涨' in three_day_trend:
        return_message=f"{three_day_trend}\n真为您感到高兴~"
    elif emotion=="高兴" and '下跌' in three_day_trend:
        return_message=f"{three_day_trend}\n请问您为什么那么高兴呢？"
    elif emotion=="悲伤" and '下跌' in three_day_trend and '上涨' in future_trend:
        return_message = f"{three_day_trend}\n但是经过我们的预测，{future_trend}"
    elif emotion == "悲伤" and '下跌' in three_day_trend and '下跌' in future_trend:
        return_message = f"{three_day_trend}\n经过我们的预测，{future_trend}\n希望您能谨慎投资呢~"
    elif emotion == "悲伤" and '上涨' in three_day_trend:
        return_message = f"{three_day_trend}\n这是好事情呀，请问您为什么难过呢？"
    else:
        return_message=f"我无法获取到您提到的股票信息，请您放平心态，理性投资~"
    return return_message


#%%
#定义转人工函数,attitude态度
def turn_human(attitude):
    if attitude == "想自杀":
        return_message="冷静，一定要冷静，现在立马为您升级人工服务~"
    else:
        return_message=""
    #真实业务中需要调用内部系统的转人工API来实现人工客服的转接
    return return_message


#%%

if __name__ == "__main__":
    # 以下为独立运行时的演示代码，避免被其它模块 import 时执行
    stock_data = pd.read_excel(STOCK_DATA_PATH, parse_dates=['Date'], sheet_name='中国银行')
    stock_data.asfreq('D')
    np.random.seed(42)
    print(stock_data)

    forecast_result = predict_future_7data(stock_name="上证指数")  # 中国银行
    print("forecast_result:", forecast_result)

    return_message = message_by_chat_policy(
        emotion="高兴",
        three_day_trend="查询到股票:上证指数,近三天的平均收盘价为:30,之前一周的平均收盘价为：25,近三天有上涨的趋势",
        future_trend=None)
    print(return_message)
