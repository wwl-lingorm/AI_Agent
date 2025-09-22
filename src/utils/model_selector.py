
from typing import Dict, Any, List
from enum import Enum
from .multi_llm_service import LLMProvider
import logging

class TaskType(Enum):
    CODE_GENERATION = "code_generation"
    CODE_ANALYSIS = "code_analysis"
    BUG_FIXING = "bug_fixing"
    CODE_REVIEW = "code_review"
    DOCUMENTATION = "documentation"

class ModelSelector:
    """智能模型选择器"""
    
    def __init__(self):
        self.logger = logging.getLogger("ModelSelector")
        
        # 模型能力映射
        self.capabilities = {
            LLMProvider.DEEPSEEK: {
                "code_generation": 9,
                "code_analysis": 8,
                "bug_fixing": 9,
                "code_review": 7,
                "documentation": 6,
                "cost": 0,  # 免费
                "speed": 8
            },
            LLMProvider.OPENAI: {
                "code_generation": 9,
                "code_analysis": 9,
                "bug_fixing": 9,
                "code_review": 8,
                "documentation": 9,
                "cost": 5,  # 较高成本
                "speed": 9
            },
            LLMProvider.TONGYI: {
                "code_generation": 8,
                "code_analysis": 8,
                "bug_fixing": 8,
                "code_review": 8,
                "documentation": 9,  # 中文文档优势
                "cost": 1,  # 低成本
                "speed": 7
            }
        }
    
    def select_best_model(self, task_type: TaskType, constraints: Dict[str, Any] = None) -> LLMProvider:
        """根据任务类型和约束选择最佳模型"""
        constraints = constraints or {}
        
        available_models = list(self.capabilities.keys())
        scored_models = []
        
        for model in available_models:
            score = self._calculate_model_score(model, task_type, constraints)
            scored_models.append((model, score))
        
        # 按分数排序，选择最高分模型
        scored_models.sort(key=lambda x: x[1], reverse=True)
        best_model = scored_models[0][0] if scored_models else LLMProvider.DEEPSEEK
        
        self.logger.info(f"为任务 {task_type.value} 选择模型: {best_model.value}")
        return best_model
    
    def _calculate_model_score(self, model: LLMProvider, task_type: TaskType, constraints: Dict[str, Any]) -> float:
        """计算模型分数"""
        capability = self.capabilities[model]
        task_capability = capability.get(task_type.value, 5)
        
        # 基础分数
        score = task_capability * 0.6
        
        # 成本约束
        max_cost = constraints.get("max_cost", float('inf'))
        if capability["cost"] <= max_cost:
            score += (10 - capability["cost"]) * 0.2
        else:
            score -= 10  # 成本超限，大幅扣分
        
        # 速度约束
        min_speed = constraints.get("min_speed", 0)
        if capability["speed"] >= min_speed:
            score += capability["speed"] * 0.2
        
        return score