"""
金融问题咨询MCP,包含2个工具:
(1) 金融问题本地RAG回复
(2) finance_news_search_consult:金融问题网络检索回复

pip install chromadb==1.0.8 #Chroma向量数据库,建议安装这个版本,高版本该代码可能会产生错误
pip install uuid #唯一id生成器
pip install dashscope #阿里云百炼平台
"""
import os
import sys
from pathlib import Path
# 确保能 import 同目录下的 function_handler
sys.path.append(str(Path(__file__).resolve().parent))
from function_handler import LLM_replay
from mcp.server.fastmcp import FastMCP
import pandas as pd
import numpy as np
import chromadb
from dotenv import load_dotenv
from typing import List,Optional,Dict,Any
# 获取当前脚本所在目录
script_dir = Path(__file__).resolve().parent
# 统一从项目根目录(上一级)加载 .env,整个工程只需维护一份配置
env_path = script_dir.parent / ".env"
load_dotenv(env_path)
#%%
#创建一个新的服务器应用实例
mcp = FastMCP("investment_consult_mcp_server", host="0.0.0.0", port=9339) #修改mcp服务端口
#%%
import pandas as pd
#使用langchain投资政策进行向量数据库的知识录入,并进行基于相似度的知识检索
# 投资政策文件与本文件同目录
POLICY_DATA_PATH = str(script_dir / "投资政策.xlsx")
# 向量数据库持久化目录,与本文件同目录
DB_DATA_DIR = str(script_dir / "db_data")
policy_info_data=pd.read_excel(POLICY_DATA_PATH)
print(policy_info_data)
#%%
import requests
#定义文本嵌入类
class QwenEmbeddingFunction:
    def __init__(self, api_key: str =os.getenv("API_KEY"), model_name: str = "text-embedding-v1"):
        """
        初始化通义千问Embedding函数
        参数:api_key: 阿里云API密钥
            model_name: 使用的embedding模型名称，默认为"text-embedding-v1"
        """
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
    def __call__(self, input: List[str]) -> List[List[float]]:
        """
        调用通义千问API获取文本的embedding
        参数:
            input: 需要embedding的文本列表 (参数名必须为input以匹配ChromaDB要求)
        返回:
            文本对应的embedding列表
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "input": {
                "texts": input
            }
        }
        response = requests.post(self.base_url, json=payload, headers=headers)
        if response.status_code != 200:
            raise Exception(f"API请求失败，状态码: {response.status_code}, 错误信息: {response.text}")
        result = response.json()
        if "output" not in result or "embeddings" not in result["output"]:
            raise Exception(f"API返回格式异常: {result}")
        # 提取embedding数据并按原始文本顺序返回
        embeddings = [None] * len(input)
        for item in result["output"]["embeddings"]:
            index = item["text_index"]
            embeddings[index] = item["embedding"]
        return embeddings

#%%
import uuid
class ChromaDBWithQwen:
    def __init__(self, collection_name: str = "policy_collection", persist_directory: str = None):
        """
        初始化ChromaDB与通义千问Embedding的集成
        参数:
            collection_name: 集合名称
            persist_directory: 数据库持久化目录
        """
        # 创建自定义的embedding函数
        self.embedding_function = QwenEmbeddingFunction(api_key=os.getenv("API_KEY"), model_name="text-embedding-v1")
        print(self.embedding_function)
        # 初始化Chroma客户端
        self.client = chromadb.PersistentClient(path=persist_directory) #path='./'
        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"} #指定向量检索模式为cos检索
        )
    def add_documents(self, documents: List[str], ids: Optional[List[str]] = None,
                     ):
        """
        添加文档到集合中
        参数:
            documents: 文档文本列表
            ids: 可选的文档ID列表
            metadatas: 可选的元数据列表
        """
        if ids is None:
            ids = [str(uuid.uuid4()) for i in range(len(documents))]
        self.collection.add(
            documents=documents,
            ids=ids,
        )
    def query_by_cosine_similarity(self, query_texts: List[str],
                                   n_results: int = 5,
                                   contract_type=None,
                                   min_similarity: Optional[float] = None) -> Dict[str, Any]:
        """
        基于余弦相似度的查询（显式使用cosine空间）
        参数:
            query_texts: 查询文本列表
            n_results: 返回的结果数量
            min_similarity: 可选的最小相似度阈值（0-1）
        返回:
            包含文档、距离、ID等信息的字典
            距离值已转换为相似度分数（1 - distance）
        """
        results = self.collection.query(
            query_texts=query_texts,
            n_results=n_results,
            include=["documents", "distances", "metadatas"]
        )
        # 将距离转换为相似度（cosine距离=1-相似度）
        if "distances" in results:
            similarities = [[1 - d for d in dist_list] for dist_list in results["distances"]]
            results["similarities"] = similarities
            # 应用相似度阈值过滤
            if min_similarity is not None:
                # 重组结果结构
                reorganized_results = {
                    "query_results": [],
                }
                for i, sim_list in enumerate(similarities):
                    query_group = []

                    for j, sim in enumerate(sim_list):
                        if sim >= min_similarity:
                            query_group.append({
                                "id": results["ids"][i][j],
                                "document": results["documents"][i][j],
                                "metadata": results["metadatas"][i][j] if results["metadatas"] else None,
                                "similarity": sim
                            })
                    reorganized_results["query_results"].append(query_group)
                return reorganized_results
        return results
document_list=list(policy_info_data['投资政策'])
print(document_list)
#%%
qwen_db=ChromaDBWithQwen(persist_directory=DB_DATA_DIR)
print(qwen_db)
#%%
# for elem in document_list:
#     qwen_db.add_documents(documents=[elem])
#%%
# result=qwen_db.query_by_cosine_similarity(query_texts=['非法或受到国际制裁的行业有哪些'],min_similarity=0.5).get("query_results",[[]]) #非法或受到国际制裁的行业有哪些
# print([k.get('document','') for k in result[0]])
#%%
#tool1:定义基于本地知识库检索的RAG函数
async def invest_policy_consult(query,db=qwen_db):
    result = qwen_db.query_by_cosine_similarity(query_texts=[query],min_similarity=0.5).get("query_results",[[]])
    print("result:",result)
    prompt_template="""你是一个知识渊博的大师,你能根据知识库中检索到的内容，回答用户问题"""
    if result!=[[]]:
        result_list=[k.get('document','') for k in result[0]]
    else:
        generate_result="我没有检索到您提问的投资政策" #我没有检索到您提问的投资政策
        return generate_result
    # 根据检索到的结果,调用LLM进行生成
    generate_result =await LLM_replay(prompt_template=prompt_template,
                                 messages="""检索结果:{}
                           用户问题:{}""".format(str(result_list), query))
    return generate_result.choices[0].message.content

#%%
#tool2:金融时政检索函数实现
import os
from http import HTTPStatus
from dashscope import Application
async def finance_news_search_consult(policy_text):
    response =Application.call(
        # 若没有配置环境变量，可用百炼API Key将下行替换为：api_key="sk-xxx"。但不建议在生产环境中直接将API Key硬编码到代码中，以减少API Key泄露风险。
        api_key=os.getenv("APP_API_KEY"), #API_KEY需要和app_id是在同一个账号下的
        app_id=os.getenv("APP_ID"),  # 替换为实际的应用 ID app_id="xxxx"
        prompt=policy_text)
    print("response:",response,"api_key:",)
    if response.status_code != HTTPStatus.OK:
        print(f'request_id={response.request_id}')
        print(f'code={response.status_code}')
        print(f'message={response.message}')
        print(f'请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code')
        return '联网查询没有找到对应的信息'
    else:
        print(response.output.text)
        return response.output.text

#%%
#工具1:金融问题政策查询RAG
@mcp.tool()
async def invest_policy_consult_tool(policy_text :str) -> str:
    """
    对于用户提供的金融问题进行知识库检索，返回问题答案
    :param policy_text:金融问题
    :return:该金融问题的答案
    """
    policy_result =await invest_policy_consult(query=policy_text)
    return policy_result

#工具2:金融政策网络检索查询RAG
@mcp.tool()
async def finance_news_search_consult_tool(policy_text :str) -> str:
    """
    对于用户提供的金融问题进行网络检索，返回问题答案
    :param policy_text:金融问题
    :return:该金融问题的答案。
    """
    policy_result =await finance_news_search_consult(policy_text)
    return policy_result


if __name__ == "__main__":
    # 以标准sse 方式运行 MCP 服务器
    mcp.run(transport='sse')
    #nohup python finance_consult_mcp_server.py &

    # 以下为可选的独立测试代码（需配置好对应API Key后取消注释运行）
    # async def main1():
    #     return_list=await invest_policy_consult(query="非法或受到国际制裁的行业有哪些")
    #     print("generate_result:",return_list)
    # asyncio.run(main1())
    #
    # async def main4():
    #     search_result=await finance_news_search_consult(policy_text="查询美国次贷危机发生的年份以及每年的GDP总额")
    #     print(search_result)
    # asyncio.run(main4())
