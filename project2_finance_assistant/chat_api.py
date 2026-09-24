"""
金融多智能体多MCP接口
pip install fastapi
"""
#%%
from fastapi import FastAPI, Request,HTTPException, Depends,Query
from fastapi.responses import RedirectResponse
import uvicorn
import json
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from multi_user_finance_assistant_main_with_session import *
#%%
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
#%%
# 访问根路径时自动跳转到 Swagger 文档页,避免浏览器打开出现 404
@app.get("/")
async def root():
    return RedirectResponse(url="/docs")

@app.post("/finance_MultiAgent_MultiMCP")
async def rag_chat_api(request: Request):
    try:
        raw_body = await request.body()
        print("raw_body:",raw_body)
        ipt = json.loads(raw_body.decode("utf-8"))
        print("ipt:",ipt)
        current_message=ipt.get("current_message","") #本轮用户会话
        session_id=ipt.get("session_id","")
        response =await chat_service(current_message=current_message,session_id=session_id)
        return {"response":response,"code":200,"msg":"success"}
    except Exception as e:
        print("出现错误")
        return {"response":"","code":500,"msg":f"service inner error:{e}"}

if __name__ == '__main__':
    http_address = "0.0.0.0"
    port=9998
    uvicorn.run(app="chat_api:app", host=http_address, port=port, workers=1)
#%%
# 服务后台启动命令
# nohup uvicorn chat_api:app --host 0.0.0.0 --port 9998 --workers 1  &
