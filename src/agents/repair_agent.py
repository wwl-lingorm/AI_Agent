from .base_agent import BaseAgent
from src.utils.multi_llm_service import MultiLLMService, LLMProvider
from typing import Dict, Any

class RepairAgent(BaseAgent):
    def __init__(self, multi_llm_service: MultiLLMService):
        super().__init__("RepairAgent", "负责生成和执行代码修复方案")
        self.llm_service = multi_llm_service
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        self.log("开始代码修复")
        preferred_model = task.get("preferred_model", "deepseek")
        provider_map = {
            "deepseek": LLMProvider.DEEPSEEK,
            "openai": LLMProvider.OPENAI,
            "tongyi": LLMProvider.TONGYI
        }
        preferred_provider = provider_map.get(preferred_model, LLMProvider.DEEPSEEK)

        # 支持批量修复 DetectionAgent 的 all_issues
        all_issues = task.get("all_issues")
        code_context_map = task.get("code_context_map")  # {file_path: code_str}
        if all_issues and code_context_map:
            results = []
            for issue in all_issues:
                file_path = issue.get("file")
                code_context = code_context_map.get(file_path)
                if not code_context:
                    results.append({"status": "error", "error": f"未找到{file_path}的代码上下文", "original_issue": issue})
                    continue
                prompt = self._build_repair_prompt(self._format_issue(issue), code_context)
                llm_result = await self.llm_service.generate_with_fallback(
                    prompt,
                    preferred_provider=preferred_provider,
                    max_tokens=2048,
                    temperature=0.3
                )
                if llm_result["success"]:
                    results.append({
                        "status": "completed",
                        "original_issue": issue,
                        "fix_suggestion": llm_result["content"],
                        "model_used": llm_result["provider"]
                    })
                else:
                    results.append({
                        "status": "error",
                        "original_issue": issue,
                        "error": llm_result["error"]
                    })
            return {
                "status": "completed",
                "repair_results": results,
                "summary": f"共修复{len(results)}个问题"
            }
        # 单个修复兼容
        issue = task.get("issue")
        code_context = task.get("code_context")
        if not issue or not code_context:
            return {"status": "error", "error": "缺少问题描述或代码上下文"}
        prompt = self._build_repair_prompt(issue, code_context)
        llm_result = await self.llm_service.generate_with_fallback(
            prompt,
            preferred_provider=preferred_provider,
            max_tokens=2048,
            temperature=0.3
        )
        if llm_result["success"]:
            return {
                "status": "completed",
                "original_issue": issue,
                "fix_suggestion": llm_result["content"],
                "model_used": llm_result["provider"],
                "summary": f"使用 {llm_result['provider']} 生成修复方案"
            }
        else:
            return {
                "status": "error",
                "error": llm_result["error"],
                "summary": "修复方案生成失败"
            }

    def _format_issue(self, issue: dict) -> str:
        """将结构化issue转为自然语言描述"""
        desc = f"文件: {issue.get('file')}, 行: {issue.get('line')}, 类型: {issue.get('type')}, 工具: {issue.get('tool')}\n问题: {issue.get('message')}"
        return desc
    
    def _build_repair_prompt(self, issue: str, code_context: str) -> str:
        """构建修复提示词"""
        return f"""
你是一个专业的代码修复AI助手。请分析以下代码问题并提供修复方案。

问题描述：
{issue}

相关代码：
```python
{code_context}
请按照以下步骤提供修复：

1.首先分析问题的根本原因

2.然后提供具体的修复方案说明

3.最后给出修复后的完整代码块

要求：

修复后的代码必须保持原有功能

代码风格要与原代码一致

添加必要的注释说明修复内容

确保没有引入新的问题

请直接给出修复后的完整代码：
"""