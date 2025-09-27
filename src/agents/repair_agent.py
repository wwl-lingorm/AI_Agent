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

        all_issues = task.get("all_issues")
        code_context_map = task.get("code_context_map")

        self.log(f"收到修复任务 - all_issues数量: {len(all_issues) if all_issues else 0}")
        self.log(f"收到修复任务 - code_context_map keys: {list(code_context_map.keys()) if code_context_map else []}")

        if all_issues is None or code_context_map is None:
            return {
                "status": "error",
                "error": "缺少问题列表或代码上下文",
                "repair_results": []
            }

        if not all_issues:
            return {
                "status": "completed",
                "repair_results": [],
                "summary": "未发现需要修复的问题"
            }

        import os
        file_path = all_issues[0].get("file")
        code_context = code_context_map.get(file_path)
        if not code_context:
            for k in code_context_map:
                if os.path.basename(k) == os.path.basename(file_path):
                    code_context = code_context_map[k]
                    break
        if not code_context:
            return {
                "status": "error",
                "error": f"未找到{file_path}的代码上下文",
                "repair_results": []
            }

        issues_text = "\n".join([self._format_issue(issue) for issue in all_issues])
        prompt = f"请修复以下Python代码中的所有问题，并给出修复后的完整代码：\n\n问题列表：\n{issues_text}\n\n原始代码：\n{code_context}"
        self.log(f"批量修复模式，问题数: {len(all_issues)}, prompt长度: {len(prompt)} 字符")
        try:
            llm_result = await self.llm_service.generate_with_fallback(
                prompt,
                preferred_provider=preferred_provider,
                max_tokens=2048,
                temperature=0.3
            )
            self.log(f"LLM批量修复结果: success={llm_result.get('success')}, error={llm_result.get('error')}, content预览={str(llm_result.get('content'))[:200]}")
        except Exception as e:
            self.log(f"LLM批量修复异常: {str(e)}")
            llm_result = {"success": False, "error": f"LLM批量修复异常: {str(e)}"}

        if llm_result["success"]:
            return {
                "status": "completed",
                "repair_results": [{
                    "status": "completed",
                    "fix_suggestion": llm_result["content"],
                    "model_used": llm_result["provider"],
                    "issues": all_issues
                }],
                "summary": f"批量修复成功，修复问题数: {len(all_issues)}",
                "code_before": code_context,
                "code_after": llm_result["content"]
            }
        else:
            return {
                "status": "error",
                "error": llm_result["error"],
                "repair_results": []
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