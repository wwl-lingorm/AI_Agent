from langchain.tools import Tool
from langchain.agents import initialize_agent
from langchain.llms import OpenAI

# 假设你已有的RepairAgent类
from .repair_agent import RepairAgent
from src.utils.multi_llm_service import MultiLLMService

# 初始化你的原有RepairAgent
multi_llm_service = MultiLLMService()
repair_agent = RepairAgent(multi_llm_service)

# 包装为LangChain Tool
def repair_tool(input_dict):
    """
    input_dict: {"code": "...", "issues": [...]}
    返回修复建议字符串
    """
    import asyncio
    task = {
        "all_issues": input_dict.get("issues", []),
        "code_context_map": {"file.py": input_dict.get("code", "")},
        "preferred_model": "deepseek"
    }
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(repair_agent.execute(task))
    return result.get("code_after", "修复失败")

repair_agent_tool = Tool(
    name="CodeRepair",
    func=repair_tool,
    description="自动修复Python代码中的静态缺陷"
)

# LangChain LLM（可用OpenAI或DeepSeek等）
llm = OpenAI(openai_api_key="sk-70484d5536f14f4a969b62e3c0e83ee3")

# 构建LangChain Agent
agent = initialize_agent(
    [repair_agent_tool],
    llm,
    agent_type="zero-shot-react-description"
)

# 示例调用
if __name__ == "__main__":
    code = "def divide(a, b):\n    return a / b"
    issues = [{"file": "file.py", "line": 1, "message": "缺少异常处理"}]
    result = agent.run({"code": code, "issues": issues})
    print("修复结果:", result)
