#!/usr/bin/env python3
"""
模拟完整流程中的RepairAgent调用
"""

import asyncio
from dotenv import load_dotenv
from src.agents.repair_agent import RepairAgent
from src.utils.multi_llm_service import MultiLLMService, LLMProvider

async def test_batch_repair():
    """测试批量修复功能（模拟完整流程）"""
    load_dotenv()
    
    llm_service = MultiLLMService()
    repair_agent = RepairAgent(llm_service)
    
    # 模拟DetectionAgent的输出
    all_issues = [
        {
            "file": "test_sample.py",
            "line": 1,
            "type": "convention",
            "message": "Missing module docstring",
            "tool": "pylint"
        },
        {
            "file": "test_sample.py",
            "line": 5,
            "type": "convention", 
            "message": "Missing function or method docstring",
            "tool": "pylint"
        }
    ]
    
    # 模拟code_context_map
    with open("test_sample.py", "r", encoding="utf-8") as f:
        code_content = f.read()
    
    code_context_map = {
        "test_sample.py": code_content
    }
    
    print("测试批量修复功能（模拟完整流程）...")
    print("=" * 60)
    print(f"问题数量: {len(all_issues)}")
    print(f"代码上下文映射: {list(code_context_map.keys())}")
    
    # 模拟CoordinatorAgent的调用
    task = {
        "type": "repair",
        "assigned_agent": "RepairAgent",
        "repo_path": "test_sample.py",
        "preferred_model": "deepseek",  # 这会导致失败并回退
        "all_issues": all_issues,
        "code_context_map": code_context_map
    }
    
    result = await repair_agent.execute(task)
    
    print(f"\n=== 批量修复结果 ===")
    print(f"状态: {result.get('status')}")
    print(f"总结: {result.get('summary')}")
    
    repair_results = result.get('repair_results', [])
    print(f"修复结果数: {len(repair_results)}")
    
    success_count = len([r for r in repair_results if r.get('status') == 'completed'])
    error_count = len([r for r in repair_results if r.get('status') == 'error'])
    print(f"成功: {success_count}, 失败: {error_count}")
    
    for i, repair_result in enumerate(repair_results, 1):
        print(f"\n--- 修复结果 {i} ---")
        print(f"状态: {repair_result.get('status')}")
        
        if repair_result.get('status') == 'completed':
            print(f"使用模型: {repair_result.get('model_used')}")
            suggestion = repair_result.get('fix_suggestion', '')
            print(f"修复建议长度: {len(suggestion)} 字符")
            print(f"修复建议预览: {suggestion[:200]}...")
        else:
            print(f"错误: {repair_result.get('error')}")
            if repair_result.get('original_issue'):
                issue = repair_result['original_issue']
                print(f"原始问题: {issue.get('file')}:{issue.get('line')} - {issue.get('message')}")

if __name__ == "__main__":
    asyncio.run(test_batch_repair())