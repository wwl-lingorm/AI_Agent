from .base_agent import BaseAgent
from src.utils.multi_llm_service import MultiLLMService, LLMProvider
from typing import Dict, Any

class RepairAgent(BaseAgent):
    def __init__(self, multi_llm_service: MultiLLMService):
        super().__init__("RepairAgent", "负责生成和执行代码修复方案")
        self.llm_service = multi_llm_service
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        self.log("开始批量文件修复")
        use_langchain = task.get("use_langchain", False)
        code_context_map = task.get("code_context_map")
        all_issues = task.get("all_issues")
        preferred_model = task.get("preferred_model", "deepseek")
        provider_map = {
            "deepseek": LLMProvider.DEEPSEEK,
            "openai": LLMProvider.OPENAI,
            "tongyi": LLMProvider.TONGYI
        }
        preferred_provider = provider_map.get(preferred_model, LLMProvider.DEEPSEEK)

        if code_context_map is None or not isinstance(code_context_map, dict):
            return {"status": "error", "error": "缺少 code_context_map 或格式错误", "repair_results": []}

        # 兼容单文件 all_issues 结构
        if all_issues is None:
            all_issues = {}
        # all_issues: {file_path: [issue, ...], ...} 或 [issue, ...]
        if isinstance(all_issues, list):
            # 单文件场景，转为 dict
            if len(code_context_map) == 1:
                file_path = list(code_context_map.keys())[0]
                all_issues = {file_path: all_issues}
            else:
                return {"status": "error", "error": "all_issues为list但有多个文件，无法对应", "repair_results": []}

        import asyncio, os
        async def repair_one_file(file_path, code, issues):
            issues_text = "\n".join([self._format_issue(issue) for issue in issues])
            prompt = f"请修复以下Python代码中的所有问题，并给出修复后的完整代码：\n\n问题列表：\n{issues_text}\n\n原始代码：\n{code}"
            self.log(f"修复文件: {file_path}, 问题数: {len(issues)}, prompt长度: {len(prompt)} 字符")
            try:
                llm_result = await self.llm_service.generate_with_fallback(
                    prompt,
                    preferred_provider=preferred_provider,
                    max_tokens=2048,
                    temperature=0.3
                )
                if llm_result["success"]:
                    return {
                        "status": "completed",
                        "file": file_path,
                        "fix_suggestion": llm_result["content"],
                        "model_used": llm_result["provider"],
                        "issues": issues,
                        "code_before": code,
                        "code_after": llm_result["content"]
                    }
                else:
                    return {
                        "status": "error",
                        "file": file_path,
                        "error": llm_result["error"],
                        "issues": issues,
                        "code_before": code
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "file": file_path,
                    "error": f"LLM修复异常: {str(e)}",
                    "issues": issues,
                    "code_before": code
                }

        # 并发修复所有文件
        tasks = []
        for file_path, code in code_context_map.items():
            issues = all_issues.get(file_path, [])
            if not isinstance(issues, list):
                issues = []
            tasks.append(repair_one_file(file_path, code, issues))

        repair_results = await asyncio.gather(*tasks)

        # 汇总所有修复结果
        success_count = sum(1 for r in repair_results if r.get("status") == "completed")
        summary = f"批量修复完成，成功: {success_count}，总文件: {len(repair_results)}"
        return {
            "status": "completed" if success_count == len(repair_results) else "partial",
            "repair_results": repair_results,
            "summary": summary
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