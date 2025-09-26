#!/usr/bin/env python3
"""
测试完整的AI Agent流程
"""

import asyncio
import sys
import os
from dotenv import load_dotenv
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.analysis_agent import AnalysisAgent
from src.agents.detection_agent import DetectionAgent
from src.agents.repair_agent import RepairAgent
from src.agents.validation_agent import ValidationAgent
from src.utils.multi_llm_service import MultiLLMService
from src.utils.model_selector import ModelSelector

async def test_full_pipeline():
    """测试完整的AI Agent流程"""
    
    # 加载环境变量
    load_dotenv()
    print("环境变量加载完成")
    
    # 初始化所有组件
    llm_service = MultiLLMService()
    print(f"可用的LLM提供商: {[p.value for p in llm_service.get_available_providers()]}")
    model_selector = ModelSelector()
    
    # 初始化所有Agent
    coordinator = CoordinatorAgent(model_selector)
    analysis_agent = AnalysisAgent()
    detection_agent = DetectionAgent()
    repair_agent = RepairAgent(llm_service)
    
    # 创建一个简单的ValidationAgent
    class SimpleValidationAgent:
        async def execute(self, task):
            return {"status": "completed", "summary": "验证跳过"}
    
    validation_agent = SimpleValidationAgent()
    
    # 注册所有Agent
    coordinator.register_agent("AnalysisAgent", analysis_agent)
    coordinator.register_agent("DetectionAgent", detection_agent)
    coordinator.register_agent("RepairAgent", repair_agent)
    coordinator.register_agent("ValidationAgent", validation_agent)
    
    # 测试文件路径
    test_file = "test_sample.py"
    
    if not os.path.exists(test_file):
        print(f"错误: 测试文件 {test_file} 不存在")
        return
    
    print(f"开始测试完整流程: {test_file}")
    print("=" * 60)
    
    # 创建任务
    task = {
        "type": "defect_analysis",
        "description": f"分析文件 {test_file} 的缺陷并修复",
        "repo_path": test_file,
        "preferred_model": "deepseek"
    }
    
    # 配置日志以显示Agent输出
    import logging
    logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
    
    # 执行完整流程
    try:
        result = await coordinator.execute(task)
        
        print("=== 流程执行结果 ===")
        print(f"状态: {result.get('status')}")
        print(f"使用模型: {result.get('model_selected')}")
        print(f"总结: {result.get('summary')}")
        
        # 详细结果
        subtask_results = result.get('subtask_results', {})
        
        for agent_name, agent_result in subtask_results.items():
            print(f"\n--- {agent_name} ---")
            print(f"状态: {agent_result.get('status')}")
            
            if agent_name == "AnalysisAgent":
                print(f"分析文件数: {agent_result.get('files_analyzed')}")
                structure = agent_result.get('structure', {})
                files = structure.get('files', [])
                if files:
                    file_info = files[0]
                    print(f"文件路径: {file_info.get('path')}")
                    print(f"函数数量: {len(file_info.get('functions', []))}")
                    print(f"类数量: {len(file_info.get('classes', []))}")
                    print(f"是否包含内容: {'是' if file_info.get('content') else '否'}")
                    if file_info.get('content'):
                        print(f"内容长度: {len(file_info.get('content'))} 字符")
            
            elif agent_name == "DetectionAgent":
                print(f"检测到缺陷数: {agent_result.get('defects_found')}")
                print(f"使用工具: {agent_result.get('tools_used')}")
                
                all_issues = agent_result.get('all_issues', [])
                if all_issues:
                    print(f"问题详情（前3个）:")
                    for i, issue in enumerate(all_issues[:3], 1):
                        print(f"  {i}. {issue.get('message')} (行:{issue.get('line')})")
            
            elif agent_name == "RepairAgent":
                print(f"总结: {agent_result.get('summary')}")
                repair_results = agent_result.get('repair_results', [])
                print(f"修复结果数: {len(repair_results)}")
                
                success_count = len([r for r in repair_results if r.get('status') == 'completed'])
                error_count = len([r for r in repair_results if r.get('status') == 'error'])
                print(f"成功: {success_count}, 失败: {error_count}")
                
                # 显示错误信息
                if error_count > 0:
                    print("错误详情:")
                    for i, repair_result in enumerate(repair_results):
                        if repair_result.get('status') == 'error':
                            print(f"  - {repair_result.get('error')}")
                            if repair_result.get('original_issue'):
                                issue = repair_result['original_issue']
                                print(f"    原始问题: {issue.get('file')}:{issue.get('line')} - {issue.get('message')}")
        
        return result
        
    except Exception as e:
        print(f"流程执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())