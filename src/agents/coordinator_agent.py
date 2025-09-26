from .base_agent import BaseAgent
from src.utils.multi_llm_service import LLMProvider
from src.utils.model_selector import ModelSelector, TaskType
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
    
    async def execute(self, task: Dict[str, Any], progress_callback=None) -> Dict[str, Any]:
        """执行协调任务（全流程自动化）"""
        self.log(f"开始处理任务: {task.get('description', '未知任务')}")
        
        # 进度回调函数
        async def update_progress(progress: int, stage: str):
            if progress_callback:
                await progress_callback(progress, stage)
        
        await update_progress(10, "正在选择最佳模型...")
        
        # 智能选择模型
        task_type = self._determine_task_type(task)
        best_model = self.model_selector.select_best_model(task_type)
        task['preferred_model'] = best_model.value

        await update_progress(20, "开始代码结构分析...")
        
        results = {}
        # 1. 代码结构分析
        analysis_task = {
            "type": "analysis",
            "assigned_agent": "AnalysisAgent",
            "repo_path": task.get("repo_path"),
            "target_files": task.get("target_files")
        }
        analysis_result = await self.agents["AnalysisAgent"].execute(analysis_task)
        results["AnalysisAgent"] = analysis_result

        await update_progress(40, "代码分析完成，开始静态检测...")

        # 2. 静态检测
        detection_task = {
            "type": "detection",
            "assigned_agent": "DetectionAgent",
            "repo_path": task.get("repo_path")
        }
        detection_result = await self.agents["DetectionAgent"].execute(detection_task)
        results["DetectionAgent"] = detection_result

        await update_progress(60, "静态检测完成，开始代码修复...")

        # 3. 自动修复（批量）
        # 构建 code_context_map: {file_path: code_str}
        import os
        code_context_map = {}
        for file_info in analysis_result.get("structure", {}).get("files", []):
            # 用basename做key，保证和issue中的file字段一致
            code_context_map[os.path.basename(file_info["path"])] = file_info.get("content") if "content" in file_info else ""
        
        self.log(f"准备修复任务 - all_issues数量: {len(detection_result.get('all_issues', []))}")
        self.log(f"准备修复任务 - code_context_map keys: {list(code_context_map.keys())}")
        
        repair_task = {
            "type": "repair",
            "assigned_agent": "RepairAgent",
            "repo_path": task.get("repo_path"),
            "preferred_model": best_model.value,
            "all_issues": detection_result.get("all_issues", []),
            "code_context_map": code_context_map
        }
        repair_result = await self.agents["RepairAgent"].execute(repair_task)
        results["RepairAgent"] = repair_result

        await update_progress(80, "代码修复完成，开始验证...")

        # 4. 自动验证（批量）
        validation_task = {
            "type": "validation",
            "assigned_agent": "ValidationAgent",
            "repo_path": task.get("repo_path"),
            "repair_results": repair_result.get("repair_results"),
            "code_context_map": code_context_map
        }
        validation_result = await self.agents["ValidationAgent"].execute(validation_task)
        results["ValidationAgent"] = validation_result

        await update_progress(95, "生成最终报告...")

        # 汇总结果
        final_result = self._aggregate_results(results)
        final_result['model_selected'] = best_model.value
        
        await update_progress(100, "任务完成")
        
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