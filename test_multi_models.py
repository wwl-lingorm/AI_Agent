import asyncio
import os
from dotenv import load_dotenv
from src.utils.multi_llm_service import MultiLLMService, LLMProvider

async def test_multi_models():
    """测试多模型功能"""
    load_dotenv()
    
    llm_service = MultiLLMService()
    
    print("可用的模型提供商:", [p.value for p in llm_service.get_available_providers()])
    
    # 测试代码生成
    test_prompt = "写一个Python函数计算斐波那契数列"
    
    print("\n=== 测试DeepSeek ===")
    result1 = await llm_service.generate_with_fallback(test_prompt, LLMProvider.DEEPSEEK)
    print(f"成功: {result1['success']}")
    print(f"提供商: {result1.get('provider', '无')}")
    print(f"内容前100字符: {result1['content'][:100]}...")
    
    print("\n=== 测试通义灵码 ===")
    result2 = await llm_service.generate_with_fallback(test_prompt, LLMProvider.TONGYI)
    print(f"成功: {result2['success']}")
    print(f"提供商: {result2.get('provider', '无')}")
    
    print("\n=== 测试自动回退 ===")
    result3 = await llm_service.generate_with_fallback(test_prompt)
    print(f"成功: {result3['success']}")
    print(f"最终使用的提供商: {result3.get('provider', '无')}")

if __name__ == "__main__":
    asyncio.run(test_multi_models())