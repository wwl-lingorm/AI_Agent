# 单条修复测试代码，便于单独验证DeepSeek修复能力
import asyncio
import os
from dotenv import load_dotenv
from src.utils.multi_llm_service import MultiLLMService, LLMProvider

async def test_single_repair():
    # 加载环境变量！
    load_dotenv()
    
    # 读取test_sample.py内容
    test_file = os.path.join(os.path.dirname(__file__), 'test_sample.py')
    with open(test_file, 'r', encoding='utf-8') as f:
        code = f.read()
    
    print(f"原始代码长度: {len(code)} 字符")
    print(f"原始代码内容（前200字符）: {code[:200]}")
    
    prompt = f"请修复以下Python代码中的所有bug并给出修复后的完整代码：\n\n{code}"
    print(f"Prompt长度: {len(prompt)} 字符")
    
    llm_service = MultiLLMService()
    print(f"可用的提供商: {[p.value for p in llm_service.get_available_providers()]}")
    
    # 启用详细日志
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    try:
        result = await llm_service.generate_with_fallback(
            prompt,
            preferred_provider=LLMProvider.DEEPSEEK,
            max_tokens=2048,
            temperature=0.3
        )
        print("单条修复测试结果：", result)
        
        # 如果失败，尝试直接调用DeepSeek适配器看详细错误
        if not result.get('success'):
            print("尝试直接调用DeepSeek适配器...")
            deepseek_adapter = llm_service.adapters.get(LLMProvider.DEEPSEEK)
            if deepseek_adapter:
                try:
                    direct_result = await deepseek_adapter.generate_code(prompt, max_tokens=2048, temperature=0.3)
                    print(f"直接调用结果: {direct_result}")
                except Exception as e:
                    print(f"直接调用异常: {str(e)}")
                    import traceback
                    traceback.print_exc()
    
    except Exception as e:
        print(f"测试异常: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_single_repair())
#!/usr/bin/env python3
"""
测试MultiLLMService
"""

import asyncio
import os
from dotenv import load_dotenv
from src.utils.multi_llm_service import MultiLLMService, LLMProvider

async def test_llm_service():
    """测试LLM服务"""
    load_dotenv()  # 加载环境变量
    
    llm_service = MultiLLMService()
    
    # 简单的测试提示
    test_prompt = """
请帮我修复这个Python代码问题：

问题：文件第1行缺少模块文档字符串

代码：
```python
import os
import sys

def divide_numbers(a, b):
    return a / b
```

请提供修复后的代码。
"""
    
    print("测试MultiLLMService...")
    print("=" * 50)
    
    try:
        result = await llm_service.generate_with_fallback(
            test_prompt,
            preferred_provider=LLMProvider.DEEPSEEK,
            max_tokens=1000,
            temperature=0.3
        )
        
        print(f"结果成功: {result['success']}")
        if result['success']:
            print(f"使用提供商: {result['provider']}")
            print(f"内容长度: {len(result['content'])} 字符")
            print(f"内容预览: {result['content'][:200]}...")
        else:
            print(f"错误: {result['error']}")
            
    except Exception as e:
        print(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm_service())