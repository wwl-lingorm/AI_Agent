#!/usr/bin/env python3
"""
测试RepairAgent的单个修复功能
"""

import asyncio
from dotenv import load_dotenv
from src.agents.repair_agent import RepairAgent
from src.utils.multi_llm_service import MultiLLMService, LLMProvider

async def test_repair_agent():
    """测试RepairAgent的单个修复"""
    load_dotenv()
    
    llm_service = MultiLLMService()
    repair_agent = RepairAgent(llm_service)
    
    # 测试问题
    test_issue = {
        "file": "test_sample.py",
        "line": 1,
        "type": "convention",
        "message": "Missing module docstring",
        "tool": "pylint"
    }
    
    # 测试代码上下文
    with open("test_sample.py", "r", encoding="utf-8") as f:
        code_context = f.read()
    
    print("测试RepairAgent单个修复...")
    print("=" * 50)
    
    # 方法1: 使用deepseek（应该失败并回退）
    task1 = {
        "issue": "文件: test_sample.py, 行: 1, 类型: convention, 工具: pylint\n问题: Missing module docstring",
        "code_context": code_context,
        "preferred_model": "deepseek"
    }
    
    print("测试1: 使用deepseek（预期会回退到tongyi）")
    result1 = await repair_agent.execute(task1)
    print(f"结果: {result1.get('status')}")
    if result1.get('status') == 'completed':
        print(f"使用模型: {result1.get('model_used')}")
        print(f"修复建议长度: {len(result1.get('fix_suggestion', ''))} 字符")
        print(f"修复建议预览: {result1.get('fix_suggestion', '')[:200]}...")
    else:
        print(f"错误: {result1.get('error')}")
    
    print("\n" + "=" * 50)
    
    # 方法2: 直接指定tongyi
    task2 = {
        "issue": "文件: test_sample.py, 行: 1, 类型: convention, 工具: pylint\n问题: Missing module docstring", 
        "code_context": code_context,
        "preferred_model": "tongyi"
    }
    
    print("测试2: 直接使用tongyi")
    result2 = await repair_agent.execute(task2)
    print(f"结果: {result2.get('status')}")
    if result2.get('status') == 'completed':
        print(f"使用模型: {result2.get('model_used')}")
        print(f"修复建议长度: {len(result2.get('fix_suggestion', ''))} 字符")
        print(f"修复建议预览: {result2.get('fix_suggestion', '')[:200]}...")
    else:
        print(f"错误: {result2.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_repair_agent())