from .base_agent import BaseAgent
from src.utils.multi_llm_service import LLMProvider
from utils.model_selector import ModelSelector, TaskType
from typing import Dict, Any, List

class CoordinatorAgent(BaseAgent):
    def __init__(self, model_selector: ModelSelector):
        super().__init__("Coordinator", "负责任务调度和协调其他Agent")
        self.agents = {}
        self.model_selector = model_selector
    
    def register_agent(self, name: str, agent: BaseAgent):
        """注册专业Agent"""
        self.agents[name] = agent
        self.log(f"注册Agent: {name}")
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行协调任务"""
        self.log(f"开始处理任务: {task.get('description', '未知任务')}")
        
        # 智能选择模型
        task_type = self._determine_task_type(task)
        best_model = self.model_selector.select_best_model(task_type)
        task['preferred_model'] = best_model.value
        
        # 任务分解逻辑
        sub_tasks = self._decompose_task(task)
        results = {}
        
        # 并行执行子任务
        for sub_task in sub_tasks:
            agent_name = sub_task['assigned_agent']
            if agent_name in self.agents:
                try:
                    result = await self.agents[agent_name].execute(sub_task)
                    results[agent_name] = result
                except Exception as e:
                    self.log(f"Agent {agent_name} 执行失败: {str(e)}", "error")
                    results[agent_name] = {"status": "error", "error": str(e)}
        
        # 汇总结果
        final_result = self._aggregate_results(results)
        final_result['model_selected'] = best_model.value
        self.log("任务处理完成")
        return final_result
    
    def _determine_task_type(self, task: Dict[str, Any]) -> TaskType:
        """根据任务内容确定任务类型"""
        task_desc = task.get('description', '').lower()
        
        if any(word in task_desc for word in ['修复', 'bug', 'defect', 'fix']):
            return TaskType.BUG_FIXING
        elif any(word in task_desc for word in ['生成', '生成代码', 'generate']):
            return TaskType.CODE_GENERATION
        elif any(word in task_desc for word in ['分析', '分析代码', 'analyze']):
            return TaskType.CODE_ANALYSIS
        else:
            return TaskType.CODE_ANALYSIS  # 默认
    
    def _decompose_task(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """将主任务分解为子任务"""
        return [
            {
                "type": "analysis",
                "assigned_agent": "AnalysisAgent",
                "repo_path": task.get("repo_path"),
                "target_files": task.get("target_files")
            },
            {
                "type": "detection", 
                "assigned_agent": "DetectionAgent",
                "repo_path": task.get("repo_path")
            },
            {
                "type": "repair",
                "assigned_agent": "RepairAgent", 
                "repo_path": task.get("repo_path"),
                "preferred_model": task.get("preferred_model", "deepseek")
            },
            {
                "type": "validation",
                "assigned_agent": "ValidationAgent",
                "repo_path": task.get("repo_path"),
                "fixed_code": task.get("fixed_code"),  # 从修复任务传递
                "original_issue": task.get("original_issue"),
                "file_path": task.get("file_path")
            }
        ]
    def _aggregate_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """汇总各Agent的结果"""
        return {
            "status": "completed",
            "subtask_results": results,
            "summary": f"处理了 {len(results)} 个子任务"
        }