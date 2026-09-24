#%%
"""
接口口请求测试
"""
import requests
from dotenv import load_dotenv
import os
from pathlib import Path
# 获取当前脚本所在目录
script_dir = Path(__file__).resolve().parent
# 加载 .env 文件
env_path = script_dir / ".env"
load_dotenv(env_path)
server_url=os.getenv("server_url")
demo_url = f"http://{server_url}:9998/finance_MultiAgent_MultiMCP"
current_message="查询一下中国石油近期收盘价数据，然后写一篇金融评论。另外，我咨询一下中国石化的创始人是谁？需要出现在金融评论中 " #那中国石油的呢 查询一下上证指数的近期的股价 查询一下中国石油近期收盘价数据，然后写一篇金融评论。另外，我咨询一下中国石化的创始人是谁？需要出现在金融评论中 股票期权是一种赋予持有者在未来某一日期以特定价格买卖股票的权利的金融衍生品。 股票期权给我介绍下是什么
# 测试请求:session_id 留空或不传则自动新建会话
_data = {"current_message":"查询一下中国石油近期收盘价数据，然后写一篇金融评论。另外，我咨询一下中国石化的创始人是谁？需要出现在金融评论中","session_id":"462c5f81-2f10-4e3d-9225-3fd3351c6e3c"}

test_response = requests.post(demo_url, json=_data,timeout=200)
print("test_response",test_response)
test_dict=test_response.json()
print(test_dict)

