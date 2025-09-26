#!/usr/bin/env python3
"""
测试不同长度的prompt对DeepSeek的影响
"""

import asyncio
import os
from dotenv import load_dotenv
from src.utils.multi_llm_service import MultiLLMService, LLMProvider

async def test_prompt_length():
    """测试不同长度的prompt"""
    load_dotenv()
    
    llm_service = MultiLLMService()
    
    # 读取test_sample.py内容
    test_file = os.path.join(os.path.dirname(__file__), 'test_sample.py')
    with open(test_file, 'r', encoding='utf-8') as f:
        full_code = f.read()
    
    # 测试1: 短prompt - 只修复一小段代码
    short_code = """def divide_numbers(a, b):
    # 没有处理除零错误
    return a / b"""
    
    short_prompt = f"请修复以下Python代码中的除零错误：\n\n{short_code}"
    
    print("=== 测试1: 短prompt ===")
    print(f"Prompt长度: {len(short_prompt)} 字符")
    
    try:
        result1 = await llm_service.generate_with_fallback(
            short_prompt,
            preferred_provider=LLMProvider.DEEPSEEK,
            max_tokens=1000,
            temperature=0.3
        )
        print(f"结果: success={result1['success']}")
        if result1['success']:
            print(f"内容预览: {result1['content'][:200]}...")
        else:
            print(f"错误: {result1['error']}")
    except Exception as e:
        print(f"异常: {str(e)}")
    
    print("\n" + "="*50 + "\n")
    
    # 测试2: 中等长度prompt - 修复一半代码
    half_code = full_code[:len(full_code)//2]
    medium_prompt = f"请修复以下Python代码中的bug：\n\n{half_code}"
    
    print("=== 测试2: 中等长度prompt ===")
    print(f"Prompt长度: {len(medium_prompt)} 字符")
    
    try:
        result2 = await llm_service.generate_with_fallback(
            medium_prompt,
            preferred_provider=LLMProvider.DEEPSEEK,
            max_tokens=1500,
            temperature=0.3
        )
        print(f"结果: success={result2['success']}")
        if result2['success']:
            print(f"内容预览: {result2['content'][:200]}...")
        else:
            print(f"错误: {result2['error']}")
    except Exception as e:
        print(f"异常: {str(e)}")
    
    print("\n" + "="*50 + "\n")
    
    # 测试3: 完整长度prompt - 修复全部代码
    full_prompt = f"请修复以下Python代码中的所有bug并给出修复后的完整代码：\n\n{full_code}"
    
    print("=== 测试3: 完整长度prompt ===")
    print(f"Prompt长度: {len(full_prompt)} 字符")
    
    try:
        result3 = await llm_service.generate_with_fallback(
            full_prompt,
            preferred_provider=LLMProvider.DEEPSEEK,
            max_tokens=2048,
            temperature=0.3
        )
        print(f"结果: success={result3['success']}")
        if result3['success']:
            print(f"内容预览: {result3['content'][:200]}...")
        else:
            print(f"错误: {result3['error']}")
            
            # 如果失败，直接调用适配器看详细错误
            print("\n尝试直接调用DeepSeek适配器...")
            deepseek_adapter = llm_service.adapters.get(LLMProvider.DEEPSEEK)
            if deepseek_adapter:
                try:
                    direct_result = await deepseek_adapter.generate_code(full_prompt, max_tokens=2048, temperature=0.3)
                    print(f"直接调用结果: {direct_result[:500]}...")
                except Exception as e:
                    print(f"直接调用异常: {str(e)}")
                    
    except Exception as e:
        print(f"异常: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_prompt_length())