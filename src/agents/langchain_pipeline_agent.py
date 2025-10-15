from langchain.tools import Tool
from langchain.agents import initialize_agent
from langchain_community.llms import OpenAI

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
    def build_tree(root_path):
        tree = {}
        code_exts = ['.py', '.ipynb', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.rb', '.php', '.cs']
        skip_dirs = {'.venv', 'venv', '__pycache__', 'node_modules', '.git', '.idea', '.vscode', 'dist', 'build', 'output', 'env', '.mypy_cache', '.pytest_cache'}
        for dirpath, dirs, files in os.walk(root_path):
            # 跳过无关/虚拟环境/缓存/第三方依赖目录
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            rel_dir = os.path.relpath(dirpath, root_path)
            if rel_dir == '.':
                rel_dir = ''
            for file in files:
                if any(file.endswith(ext) for ext in code_exts):
                    rel_file = os.path.join(rel_dir, file) if rel_dir else file
                    tree[rel_file] = os.path.join(dirpath, file)
        return tree

    if os.path.isfile(repo_path) and repo_path.endswith('.py'):
        file_tree = {os.path.basename(repo_path): repo_path}
    elif os.path.isdir(repo_path):
        file_tree = build_tree(repo_path)
    else:
        return {"error": "路径无效或不支持的文件类型"}

    import asyncio
    results = {}
    # 控制最大并发数，提升分析速度（如遇内存/配额问题可调低）
    SEMAPHORE_LIMIT = 8
    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

    async def process_file(rel_path, abs_path):
        async with semaphore:
            # 静态检测
            detection_result = await detection_tool({"repo_path": abs_path})
            # 保留检测原始结果用于展示
            issues = detection_result.get("all_issues", [])
            # 过滤低优先级问题（如 convention/info），只保留 error/warning/runtime
            def filter_issues(issues_list):
                high = []
                for it in issues_list:
                    t = ''
                    if isinstance(it.get('type'), str):
                        t = it.get('type')
                    elif isinstance(it.get('severity'), str):
                        t = it.get('severity')
                    else:
                        t = str(it)
                    tl = t.lower()
                    if 'error' in tl or 'warn' in tl or 'runtime' in tl or 'critical' in tl or 'fatal' in tl:
                        high.append(it)
                return high
            high_issues = filter_issues(issues)
            code_context_map = {}
            # 结构分析
            analysis_result = await analysis_tool({"repo_path": abs_path})
            if analysis_result.get("structure") and analysis_result["structure"].get("files"):
                code_context_map = {f["path"]: f["content"] for f in analysis_result["structure"]["files"]}
            # 修复（静态+动态） — 仅对高优先级问题执行修复
            repair_result = await repair_tool({"all_issues": high_issues, "code_context_map": code_context_map})
            repair_results = []
            for idx, r in enumerate(repair_result.get("repair_results", [])):
                code_after = r.get("fix_suggestion")
                issue = high_issues[idx] if idx < len(high_issues) else (r.get("issues")[0] if r.get("issues") else {})
                repair_results.append({
                    "original_issue": issue,
                    "file": issue.get("file") if issue else rel_path,
                    "fixed_code": code_after,
                    "fix_suggestion": code_after,
                    **r
                })
            # 验证
            validation_result = await validation_tool({
                "repo_path": repo_path,
                "repair_results": repair_results,
                "code_context_map": code_context_map
            })
            return rel_path, {
                "detection": detection_result,
                "analysis": analysis_result,
                "repair": repair_result,
                "validation": validation_result
            }

    # 分批处理所有文件
    tasks = [process_file(rel_path, abs_path) for rel_path, abs_path in file_tree.items()]
    for fut in asyncio.as_completed(tasks):
        rel_path, result = await fut
        results[rel_path] = result
    return results

if __name__ == "__main__":
    repo_path = "你的代码路径"
    result = asyncio.run(pipeline_run(repo_path))
    print(result)
