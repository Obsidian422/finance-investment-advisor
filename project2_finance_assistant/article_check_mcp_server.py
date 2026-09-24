"""
定义金融风险审查MCP,包含以下四个工具：
(1) 规范性审查工具
(2) 专业性检索工具
(3) 基于两个审查结果，生成风险审查报告工具
(4) 基于两个审查结果，修改原文档生成新的高质量文章
"""
import os
from typing import Any
from function_handler import LLM_replay
from mcp.server.fastmcp import FastMCP

# 当前文件所在目录,金融docx文件与本文件同目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

mcp = FastMCP("article_check_mcp_server", host="0.0.0.0", port=9330) #修改mcp服务端口
#定义规范性审查的函数
async def basic_check(file_text):
    prompt_template="""你是一个金融文本检查助手,你善于对用户提供的金融文本基于内容规范性的检查并返回修改建议，检查的维度包括:
    (1) 错别字检查
    (2) 是否存在不符合金融类文件严谨正式、含糊的表达
    (3) 语句不通顺连贯
    (4) 内容是否存在重复
    (5) 内容是否存在前后矛盾
    举例:
    输入:题目：股市大涨，投资者如何应对？
    最近，股市行情一片大好，各大指数纷纷上涨，投资者们纷纷涌入市场，生怕错过这波行情。但是，市场行情虽然好，但风险也不可忽视。很多投资者盲目跟风，导致亏损惨重。
    从历史数据来看，股市的上涨往往伴随着回调。回调是股市的正常现象，不必过于担心。但是，如果投资者没有做好风险管理，可能会在回调中遭受巨大损失。因此，投资者应该谨慎操作，不要盲目追高。
    另外，市场的流动性也很重要。流动性好的股票更容易买卖，流动性差的股票可能会让投资者陷入困境。所以，投资者在选择股票时，一定要关注流动性。流动性是衡量股票交易活跃度的重要指标。
    不过，虽然股市现在表现很好，但未来走势仍不确定。有的分析师认为牛市还会持续，有的则认为市场即将见顶。投资者应该根据自己的风险承受能力，制定合理的投资策略。
    输出:文章规范性审查意见
    1、错别字：无明显错别字，但部分表达不够精准，如“市场行情虽然好”可优化为“尽管市场行情良好”。
    2、非严谨的表达：“股市行情一片大好”过于主观，可改为“近期股市呈现上涨趋势”。“投资者们纷纷涌入市场”不够严谨，可补充数据支撑，如“根据XX数据，近期开户数增长XX%”。
    3、语句不通顺：“回调是股市的正常现象，不必过于担心。但是，如果投资者没有做好风险管理……”前后逻辑稍显矛盾，可调整为：“回调是股市的正常现象，但若投资者未做好风险管理，仍可能遭受损失。”
    4、前后重复：“流动性”相关内容重复出现，可合并为：“流动性是衡量股票交易活跃度的重要指标，投资者应优先选择流动性较好的股票，以降低买卖难度。”
    5、前后矛盾：开头强调“股市大涨”，后文又说“未来走势不确定”，可调整表述逻辑，如：“尽管近期股市表现强劲，但未来走势仍存在不确定性，投资者需保持警惕。”"""
    check_result=await LLM_replay(prompt_template=prompt_template,messages='输入'+file_text+'\n'+'输出:')
    return check_result.choices[0].message.content

#定义专业性审查的函数实现
async def professional_check(file_text):
    prompt_template="""你是一个金融文本审查助手,你善于对用户提供的金融文本基于内容专业性的检查并返回修改建议，检查的维度包括:
    (1) 是否存在潜在财务风险
    (2) 是否存在潜在税务风险
    (3) 是否存在潜在法律风险
    (4) 是否存在金融合规风险
    (5) 是否存在消费者欺诈投诉风险
    举例:
    输入:高收益基金：快速致富的捷径？
    近年来，高收益基金凭借其诱人的回报率吸引了大量投资者。许多基金公司宣称，通过投资未上市企业、房地产或海外资产，年化收益率可达20%以上，远超银行存款和传统理财。然而，高收益往往伴随高风险，投资者在追逐利润的同时，可能忽视了一些关键问题。
    1. 高收益基金的运作模式
    这类基金通常采用“滚动投资”策略，即用新投资者的资金支付老投资者的收益，而非依赖实际投资收益。虽然短期内能维持高回报，但一旦资金链断裂，可能导致巨额亏损。此外，部分基金未在监管机构备案，投资者难以核实其真实运作情况。
    2. 税务优化还是税务风险？
    某些基金宣传“税务优化方案”，承诺帮助投资者规避资本利得税。然而，此类操作可能涉及灰色地带，甚至违反税法。一旦被税务部门稽查，投资者可能面临补税、罚款甚至法律责任。
    3. 法律合规性存疑
    部分基金以“私募”名义募集资金，却向不特定公众推销，违反《证券投资基金法》相关规定。此外，基金合同条款模糊，投资者维权困难。
    4. 警惕“保本承诺”陷阱
    某些销售人员口头承诺“保本保收益”，但合同并未载明，属于典型的误导性宣传。投资者一旦遭遇亏损，可能因证据不足难以索赔。
    输出:文章专业性审查意见
    1、潜在财务风险:文章提到“滚动投资”模式可能引发资金链断裂，但未明确提示庞氏骗局风险。建议修改为:补充说明此类运作模式可能涉嫌庞氏骗局，并举例历史案例（如e租宝）。
    2、潜在税务风险:未具体说明“税务优化”可能涉及的逃税行为。建议修改为:明确提示“税务优化”若采用虚假交易或离岸架构，可能构成逃税，并建议投资者咨询专业税务顾问。
    3、潜在法律风险:未强调向公众募集资金的非法性及可能的法律后果。建议补充《证券法》相关规定，明确此类行为可能被认定为非法集资，投资者可向证监会举报。
    4、金融合规风险:"未提及基金是否具备合规资质（如私募基金管理人登记）。建议增加投资者在“中国证券投资基金业协会”官网核查基金备案信息。
    5、消费者欺诈投诉风险:“保本承诺”部分未提供投诉渠道或监管机构联系方式。建议增加提示：若遇虚假宣传，可向12386证监会热线或当地金融监管局投诉。"""
    check_result=await LLM_replay(prompt_template=prompt_template,messages='输入'+file_text+'\n'+'输出:')
    return_message=check_result.choices[0].message.content
    return return_message

#定义基于规范性和专业性审查结果,生成审查报告的MCP
async def produce_check_result_report(basic_check_result,professional_check_result):
    prompt_template="""你是一个金融审查报告生成大师,你善于基于用户提供的专业性和规范性审查结果，基于以下提纲生成一份审查报告
    1、审查目的：帮助用户解决文本审查各项不专业性、风险点
    2、关键风险点：说明最重要的核心风险项，通常会造成巨大财务危机及品牌影响或极其重要的事件
    3、分维度审查剖析：分不同维度概括性的分析审查中发现的问题
    4、修改建议：根据审查出的问题，汇总修改建议\n"""
    message_input="文章专业性审查意见:"+"\n"+professional_check_result+"文章规范性审查意见:"+"\n"+basic_check_result+"\n"
    check_result=await LLM_replay(prompt_template=prompt_template,messages='输入:'+message_input+'\n'+'输出:')
    return_message = check_result.choices[0].message.content
    return return_message

#基于规范性和专业性审查结果，对原文章进行缺陷改进，生成改良后的文章
async def produce_refine_report(basic_check_result,professional_check_result,file_text):
    prompt_template="""你是一个金融文章生成大师,你善于根据提供的专业性和规范性审查点，改进原文章，生成一份新的无专业性与规范性缺陷的文章\n"""
    message_input=f"""
    原文章:{file_text}
    文章规范性审查意见:{basic_check_result}
    文章专业性审查意见:{professional_check_result}
    修改后的文章:"""
    check_result=await LLM_replay(prompt_template=prompt_template,messages=message_input)
    return_message = check_result.choices[0].message.content
    return return_message
#%%
# 定义一个从url上获取文件对应的文字流数据的方法，这里我就从本地读取文件模拟从云平台读取链接的过程 oss存储
# pip install python-docx
import requests
from io import BytesIO
import docx
import sys
def docx_to_text(filename):
    """
    从本地读取.docx文件并将其内容转换为文字流
    参数:
        filename (str): 要读取的.docx文件的路径
    返回:
        str: 文档内容的文本表示
    """
    try:
        # 打开文档
        doc = docx.Document(os.path.join(BASE_DIR, filename))
        # 提取所有段落的文本
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        # 将所有段落文本合并为一个字符串
        return '\n'.join(full_text)
    except FileNotFoundError:
        print(f"错误: 文件 '{filename}' 不存在。")
        return None
    except Exception as e:
        print(f"处理文件时出错: {e}")
        return None

# doc_url="全球增长基金的表现与风险分析.docx"
# return_docs=docx_to_text(filename="全球增长基金的表现与风险分析.docx")
# print(return_docs)
#%%
#工具1:规范性审查MCP
@mcp.tool()
async def basic_check_tool(filename :str) -> str:
    """
    给予用户提供的金融文本进行规范性审查,返回审查结果
    :param filename:用户提供带后缀的金融docx文件名称，例如：银行利息.docx,银行利息.doc
    :return:存在问题的审查项。
    """
    file_text=docx_to_text(filename)
    check_items =await basic_check(file_text)
    return check_items

#工具2:专业性审查MCP
@mcp.tool()
async def professional_check_tool(filename :str) -> str:
    """
    给予用户提供的文本进行专业性审查,返回审查结果
    :param filename:用户提供带后缀的金融docx文件名称，例如：银行利息.docx,银行利息.doc
    :return:存在问题的审查项。
    """
    file_text = docx_to_text(filename)
    check_items =await professional_check(file_text)
    return check_items

#工具3:基于专业性审查与规范性审查结果生成审查分析报告
@mcp.tool()
async def produce_check_result_report_tool(basic_check_result :str,professional_check_result :str) -> str:
    """
    输入文章专业性检查意见与规范性审查意见，综合内容生成一份审查报告
    :param basic_check_result:规范性审查意见
    :param professional_check_result:专业性审查意见
    :return:审查报告
    """
    check_reports =await produce_check_result_report(basic_check_result,professional_check_result)
    return check_reports

#工具4：基于专业性审查与规范性审查结果，对原文档进行修改生成修改后的高质量金融文章
@mcp.tool()
async def produce_refine_report_tool(basic_check_result :str,professional_check_result :str,filename: str) -> str:
    """
    输入文章专业性检查意见与规范性审查意见，对原文章进行缺陷改进，生成改良后的文章
    :param basic_check_result:规范性审查意见
    :param professional_check_result:专业性审查意见
    :param filename:用户提供带后缀的金融docx文件名称，例如：银行利息.docx,银行利息.doc
    :return:改进后的金融类文章
    """
    file_text = docx_to_text(filename)
    refine_art_results =await produce_refine_report(basic_check_result,professional_check_result,file_text)
    return refine_art_results

if __name__ == "__main__":
    # 以标准 I/O 方式运行 MCP 服务器
    mcp.run(transport='sse')

    #nohup python article_check_mcp_server.py &
