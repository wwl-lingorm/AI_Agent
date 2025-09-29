from langchain.tools import Tool
from langchain.agents import initialize_agent
from langchain.llms import OpenAI

from .analysis_agent import AnalysisAgent
from .repair_agent import RepairAgent
from .validation_agent import ValidationAgent
from .detection_agent import DetectionAgent
from src.utils.multi_llm_service import MultiLLMService

multi_llm_service = MultiLLMService()
analysis_agent = AnalysisAgent()
repair_agent = RepairAgent(multi_llm_service)
validation_agent = ValidationAgent()
detection_agent = DetectionAgent()

# Tool: 分析
async def analysis_tool(input_dict):
    """
    input_dict: {"repo_path": "..."}
    返回分析结果
    """
    result = await analysis_agent.execute({"repo_path": input_dict.get("repo_path")})
    return result

# Tool: 修复
async def repair_tool(input_dict):
    """
    input_dict: {"all_issues": [...], "code_context_map": {...}}
    返回修复结果
    """
    result = await repair_agent.execute(input_dict)
    return result

# Tool: 测试/验证
async def validation_tool(input_dict):
    """
    input_dict: {"repo_path": "...", "repair_results": [...], "code_context_map": {...}}
    返回验证结果
    """
    result = await validation_agent.execute(input_dict)
    return result

# Tool: 缺陷检测
async def detection_tool(input_dict):
    """
    input_dict: {"repo_path": "..."}
    返回检测结果
    """
    result = await detection_agent.execute({"repo_path": input_dict.get("repo_path")})
    return result

analysis_tool_obj = Tool(
    name="CodeAnalysis",
    func=analysis_tool,
    description="分析代码结构和发现问题"
)
repair_tool_obj = Tool(
    name="CodeRepair",
    func=repair_tool,
    description="自动修复Python代码中的静态缺陷"
)
validation_tool_obj = Tool(
    name="CodeValidation",
    func=validation_tool,
    description="验证修复后的代码质量和正确性"
)
detection_tool_obj = Tool(
    name="CodeDetection",
    func=detection_tool,
    description="检测Python代码中的静态缺陷"
)

llm = OpenAI(openai_api_key="sk-70484d5536f14f4a969b62e3c0e83ee3")

# 构建统一LangChain Agent
agent = initialize_agent(
    [detection_tool_obj, analysis_tool_obj, repair_tool_obj, validation_tool_obj],
    llm,
    agent_type="zero-shot-react-description"
)

# 示例：统一调度检测-分析-修复-测试
import asyncio
import os
async def pipeline_run(repo_path):
    # 递归收集所有py文件
    file_list = []
    if os.path.isfile(repo_path) and repo_path.endswith('.py'):
        file_list = [repo_path]
    elif os.path.isdir(repo_path):
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                if file.endswith('.py'):
                    file_list.append(os.path.join(root, file))
    else:
        return {"error": "路径无效或不支持的文件类型"}

    results = {}
    for file_path in file_list:
        # 缺陷检测
        detection_result = await detection_tool({"repo_path": file_path})
        issues = detection_result.get("all_issues", [])
        code_context_map = {}
        # 结构分析（可选，补充结构信息）
        analysis_result = await analysis_tool({"repo_path": file_path})
        if analysis_result.get("structure") and analysis_result["structure"].get("files"):
            code_context_map = {f["path"]: f["content"] for f in analysis_result["structure"]["files"]}
        # 修复
        repair_result = await repair_tool({"all_issues": issues, "code_context_map": code_context_map})
        # 组织修复结果列表，补充 original_issue、file_path、fixed_code 字段，供验证用
        repair_results = []
        for idx, r in enumerate(repair_result.get("repair_results", [])):
            # 兼容 fix_suggestion 为修复后代码
            code_after = r.get("fix_suggestion")
            # 取第一个 issue 作为原始问题
            issue = issues[idx] if idx < len(issues) else (r.get("issues")[0] if r.get("issues") else {})
            repair_results.append({
                "original_issue": issue,
                "file": issue.get("file") if issue else file_path,
                "fixed_code": code_after,
                "fix_suggestion": code_after,
                **r
            })
        # 验证（传递修复结果、代码上下文、repo_path）
        validation_result = await validation_tool({
            "repo_path": repo_path,
            "repair_results": repair_results,
            "code_context_map": code_context_map
        })
        results[file_path] = {
            "detection": detection_result,
            "analysis": analysis_result,
            "repair": repair_result,
            "validation": validation_result
        }
    return results

if __name__ == "__main__":
    repo_path = "你的代码路径"
    result = asyncio.run(pipeline_run(repo_path))
    print(result)
