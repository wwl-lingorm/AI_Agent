#!/usr/bin/env python3
"""
测试DetectionAgent对test_sample.py的检测能力
"""

import asyncio
import sys
import os
from src.agents.detection_agent import DetectionAgent

async def test_detection_agent():
    """测试检测代理对test_sample.py的检测能力"""
    
    # 初始化检测代理
    detection_agent = DetectionAgent()
    
    # 测试文件路径
    test_file = "test_sample.py"
    
    if not os.path.exists(test_file):
        print(f"错误: 测试文件 {test_file} 不存在")
        return
    
    print(f"开始检测文件: {test_file}")
    print("=" * 50)
    
    # 创建任务
    task = {
        "repo_path": test_file,  # 单文件检测
        "type": "defect_detection"
    }
    
    # 执行检测
    result = await detection_agent.execute(task)
    
    # 打印结果
    print(f"检测状态: {result.get('status')}")
    print(f"检测到的缺陷数量: {result.get('defects_found', 0)}")
    print(f"使用的语言: {result.get('language')}")
    print(f"使用的工具: {result.get('tools_used', [])}")
    
    print("\n" + "=" * 50)
    print("详细分析结果:")
    
    analysis_results = result.get('analysis_results', {})
    for tool, tool_result in analysis_results.items():
        print(f"\n--- {tool.upper()} 结果 ---")
        print(f"工具可用: {tool_result.get('available', False)}")
        
        if tool_result.get('error'):
            print(f"错误: {tool_result['error']}")
        
        # 添加调试信息
        if tool_result.get('stdout'):
            print(f"标准输出长度: {len(tool_result['stdout'])}")
        if tool_result.get('stderr'):
            print(f"标准错误: {tool_result['stderr'][:200]}...")
        
        issues = tool_result.get('issues', [])
        print(f"发现问题数: {len(issues)}")
        
        for i, issue in enumerate(issues, 1):
            print(f"\n问题 {i}:")
            print(f"  文件: {issue.get('file', 'N/A')}")
            print(f"  行号: {issue.get('line', 'N/A')}")
            print(f"  类型: {issue.get('type', 'N/A')}")
            print(f"  消息: {issue.get('message', 'N/A')}")
            if issue.get('symbol'):
                print(f"  符号: {issue.get('symbol')}")
            if issue.get('severity'):
                print(f"  严重性: {issue.get('severity')}")
    
    # 检查是否检测到关键问题
    print("\n" + "=" * 50)
    print("关键问题检查:")
    
    all_issues = result.get('all_issues', [])
    
    # 检查除零错误
    division_issues = [issue for issue in all_issues if 'divide' in issue.get('message', '').lower() or 'zero' in issue.get('message', '').lower()]
    print(f"除零相关问题: {len(division_issues)} 个")
    
    # 检查未使用的变量
    unused_var_issues = [issue for issue in all_issues if 'unused' in issue.get('message', '').lower() and 'variable' in issue.get('message', '').lower()]
    print(f"未使用变量问题: {len(unused_var_issues)} 个")
    
    # 检查未使用的函数
    unused_func_issues = [issue for issue in all_issues if 'unused' in issue.get('message', '').lower() and ('function' in issue.get('message', '').lower() or 'import' in issue.get('message', '').lower())]
    print(f"未使用函数/导入问题: {len(unused_func_issues)} 个")
    
    # 检查硬编码路径
    hardcode_issues = [issue for issue in all_issues if 'hardcode' in issue.get('message', '').lower() or 'path' in issue.get('message', '').lower()]
    print(f"硬编码路径问题: {len(hardcode_issues)} 个")
    
    # 检查异常处理
    exception_issues = [issue for issue in all_issues if 'exception' in issue.get('message', '').lower() or 'error' in issue.get('message', '').lower()]
    print(f"异常处理问题: {len(exception_issues)} 个")
    
    return result

if __name__ == "__main__":
    asyncio.run(test_detection_agent())