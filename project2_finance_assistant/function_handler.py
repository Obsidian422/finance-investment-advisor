"""
项目二的公共函数定义
pip install openai
pip install dotenv
"""
#%%
from dotenv import load_dotenv
import os
import asyncio
from openai import AsyncOpenAI
import os
from pathlib import Path
# 获取当前脚本所在目录
script_dir = Path(__file__).resolve().parent
# 统一从项目根目录(上一级)加载 .env,整个工程只需维护一份配置
env_path = script_dir.parent / ".env"
load_dotenv(env_path)

# project1 数据文件目录(与本文件所在目录同级)
PROJECT1_DIR = script_dir.parent / "project1_stock_counselor"
STOCK_DATA_PATH = str(PROJECT1_DIR / "stock_data.xlsx")

# ===== 统一 LLM 配置(支持 qwen / deepseek 切换)=====
# 通过环境变量 LLM_PROVIDER 选择驱动模型,取值:qwen(默认) 或 deepseek
# 选 qwen     -> 只需配置 API_KEY(阿里云 DashScope)
# 选 deepseek -> 只需配置 DEEPSEEK_API_KEY(DeepSeek 官网,须支持 function calling)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "qwen").lower()

if LLM_PROVIDER == "deepseek":
    LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    LLM_BASE_URL = "https://api.deepseek.com"
    LLM_MODEL = "deepseek-chat"
else:  # 默认 qwen
    LLM_API_KEY = os.getenv("API_KEY")
    LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    LLM_MODEL = "qwen3.7-plus"

if not LLM_API_KEY:
    raise ValueError(
        f"未找到 LLM_API_KEY。当前 LLM_PROVIDER={LLM_PROVIDER}，"
        f"请在 .env 中配置对应的 {'DEEPSEEK_API_KEY' if LLM_PROVIDER == 'deepseek' else 'API_KEY'}"
    )
print(f"[LLM配置] provider={LLM_PROVIDER}, model={LLM_MODEL}, base_url={LLM_BASE_URL}")

#定义大模型调用函数，用于处理文本类审查、生成工作
async def LLM_replay(prompt_template,messages):
    """
    prompt_template:大模型调用的提示词模板
    message:大模型调用的用户输入
    """
    llm_client =AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    result =await llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role":"system","content":prompt_template},{"role":"user","content":messages}],
        max_tokens=8192,
        temperature=0)
    return result
# result=await LLM_replay(prompt_template="你是一个AI聊天助手",messages="你好")
# async def main():
#     result=await LLM_replay(prompt_template="你是一个AI聊天助手",messages="你好")
#     print("result:",result.choices[0].message.content)
#
# asyncio.run(main())

#%%
import pandas as pd
import numpy as np
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.arima.model import ARIMA
# from matplotlib import pyplot as plt
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


#%%
if __name__ == "__main__":
    # 以下为独立运行时的演示代码，避免被其它模块 import 时执行
    stock_data = pd.read_excel(STOCK_DATA_PATH, parse_dates=['Date'], sheet_name='中国银行')
    stock_data.asfreq('D')
    np.random.seed(42)
    print(stock_data)
