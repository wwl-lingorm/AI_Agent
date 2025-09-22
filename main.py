import asyncio
import os
from dotenv import load_dotenv
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.analysis_agent import AnalysisAgent
from src.agents.detection_agent import DetectionAgent
from src.agents.repair_agent import RepairAgent
from src.utils.multi_llm_service import MultiLLMService
from utils.model_selector import ModelSelector

class MultiAgentSystem:
    def __init__(self):
        load_dotenv()  # 加载环境变量
        
        # 初始化服务
        self.llm_service = MultiLLMService()
        self.model_selector = ModelSelector()
        
        # 初始化Agent
        self.coordinator = CoordinatorAgent(self.model_selector)
        self.analysis_agent = AnalysisAgent()
        self.detection_agent = DetectionAgent()
        self.repair_agent = RepairAgent(self.llm_service)
        
        # 注册Agent
        self._register_agents()
        
        # 显示可用模型
        self._show_available_models()
    
    def _register_agents(self):
        """注册所有Agent到协调器"""
        self.coordinator.register_agent("AnalysisAgent", self.analysis_agent)
        self.coordinator.register_agent("DetectionAgent", self.detection_agent)
        self.coordinator.register_agent("RepairAgent", self.repair_agent)
    
    def _show_available_models(self):
        """显示可用的模型"""
        available_models = self.llm_service.get_available_providers()
        print("=== 可用的AI模型 ===")
        for model in available_models:
            print(f"- {model.value}")
        print("====================")
    
    async def run_defect_analysis(self, repo_path: str, preferred_model: str = None):
        """运行缺陷分析流程"""
        task = {
            "type": "defect_analysis",
            "description": f"分析代码库 {repo_path} 的缺陷",
            "repo_path": repo_path,
            "target_files": None,
            "preferred_model": preferred_model  # 可选：指定偏好模型
        }
        
        result = await self.coordinator.execute(task)
        return result

async def main():
    # 初始化系统
    system = MultiAgentSystem()
    
    # 测试代码库路径（替换为你的项目路径）
    test_repo = "/path/to/your/project"
    
    if not os.path.exists(test_repo):
        print(f"测试路径不存在: {test_repo}")
        print("请修改main.py中的test_repo变量为你的项目路径")
        return
    
    # 运行缺陷分析
    print("开始运行多Agent缺陷检测系统...")
    
    # 可以指定偏好模型（可选）
    result = await system.run_defect_analysis(test_repo, preferred_model="deepseek")
    
    # 打印结果
    print("\n=== 分析结果 ===")
    print(f"状态: {result.get('status')}")
    print(f"使用的模型: {result.get('model_selected', '未知')}")
    print(f"总结: {result.get('summary')}")
    
    # 详细结果
    subtask_results = result.get('subtask_results', {})
    for agent_name, agent_result in subtask_results.items():
        print(f"\n{agent_name}: {agent_result.get('summary', '无总结')}")
        if agent_name == "RepairAgent" and agent_result.get('status') == 'completed':
            print(f"  模型: {agent_result.get('model_used')}")
            print(f"  修复建议: {agent_result.get('fix_suggestion', '无')[:200]}...")

if __name__ == "__main__":
    asyncio.run(main())