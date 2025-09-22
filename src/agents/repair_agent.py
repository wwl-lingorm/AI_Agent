from .base_agent import BaseAgent
from src.utils.multi_llm_service import MultiLLMService, LLMProvider
from typing import Dict, Any

class RepairAgent(BaseAgent):
    def __init__(self, multi_llm_service: MultiLLMService):
        super().__init__("RepairAgent", "负责生成和执行代码修复方案")
        self.llm_service = multi_llm_service
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        self.log("开始代码修复")
        
        issue = task.get("issue")
        code_context = task.get("code_context")
        preferred_model = task.get("preferred_model", "deepseek")  # 支持指定模型
        
        if not issue or not code_context:
            return {"status": "error", "error": "缺少问题描述或代码上下文"}
        
        # 根据偏好选择模型提供商
        provider_map = {
            "deepseek": LLMProvider.DEEPSEEK,
            "openai": LLMProvider.OPENAI, 
            "tongyi": LLMProvider.TONGYI
        }
        preferred_provider = provider_map.get(preferred_model, LLMProvider.DEEPSEEK)
        
        # 构建修复提示词
        prompt = self._build_repair_prompt(issue, code_context)
        
        # 使用多模型服务生成修复方案
        llm_result = await self.llm_service.generate_with_fallback(
            prompt, 
            preferred_provider=preferred_provider,
            max_tokens=2048,
            temperature=0.3  # 较低温度以获得更确定的代码
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