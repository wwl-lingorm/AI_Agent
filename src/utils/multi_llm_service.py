import os
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from enum import Enum
import logging

class LLMProvider(Enum):
    DEEPSEEK = "deepseek"
    OPENAI = "openai"  # 用于GitHub Copilot（OpenAI兼容接口）
    TONGYI = "tongyi"  # 通义灵码
    COHERE = "cohere"  # 备选免费模型
    OLLAMA = "ollama"  # 本地部署模型

class BaseLLMAdapter(ABC):
    """基础LLM适配器接口"""
    
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key
        self.base_url = base_url
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def generate_code(self, prompt: str, **kwargs) -> str:
        """生成代码"""
        pass
    
    @abstractmethod
    async def chat_complete(self, messages: List[Dict], **kwargs) -> str:
        """聊天补全"""
        pass
    
    @abstractmethod
    def get_cost_estimate(self, prompt_tokens: int, completion_tokens: int) -> float:
        """估算成本"""
        pass

class DeepSeekAdapter(BaseLLMAdapter):
    """DeepSeek适配器"""
    
    async def generate_code(self, prompt: str, **kwargs) -> str:
        try:
            # 简化实现，实际使用时安装 deepseek-api 包
            import requests
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "deepseek-coder",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": kwargs.get("max_tokens", 2048),
                "temperature": kwargs.get("temperature", 0.7)
            }
            
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            # 打印原始响应内容
            import sys
            exc_type, exc_value, exc_tb = sys.exc_info()
            response_text = None
            if hasattr(e, 'response') and e.response is not None:
                try:
                    response_text = e.response.text
                    print("DeepSeek原始响应：", response_text)
                except Exception:
                    pass
            self.logger.error(f"DeepSeek API调用失败: {str(e)}; 原始响应: {response_text}")
            return f"DeepSeek错误: {str(e)}; 原始响应: {response_text}"
    
    async def chat_complete(self, messages: List[Dict], **kwargs) -> str:
        # 与generate_code类似，可以根据需要调整
        prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])
        return await self.generate_code(prompt, **kwargs)
    
    def get_cost_estimate(self, prompt_tokens: int, completion_tokens: int) -> float:
        # DeepSeek免费，成本为0
        return 0.0

class OpenAIAdapter(BaseLLMAdapter):
    """OpenAI适配器（用于GitHub Copilot等）"""
    
    async def generate_code(self, prompt: str, **kwargs) -> str:
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            
            response = client.chat.completions.create(
                model=kwargs.get("model", "gpt-3.5-turbo"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", 2048),
                temperature=kwargs.get("temperature", 0.7)
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"OpenAI API调用失败: {str(e)}")
            return f"OpenAI错误: {str(e)}"
    
    async def chat_complete(self, messages: List[Dict], **kwargs) -> str:
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            
            response = client.chat.completions.create(
                model=kwargs.get("model", "gpt-3.5-turbo"),
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 2048),
                temperature=kwargs.get("temperature", 0.7)
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"OpenAI聊天完成失败: {str(e)}")
            return f"OpenAI错误: {str(e)}"
    
    def get_cost_estimate(self, prompt_tokens: int, completion_tokens: int) -> float:
        # 粗略估算，实际根据模型定价不同
        return (prompt_tokens * 0.0015 + completion_tokens * 0.002) / 1000  # 美元

class TongyiAdapter(BaseLLMAdapter):
    """通义灵码适配器"""
    
    async def generate_code(self, prompt: str, **kwargs) -> str:
        try:
            import dashscope
            dashscope.api_key = self.api_key
            
            from dashscope import Generation
            response = Generation.call(
                model="qwen-plus",
                prompt=prompt,
                max_tokens=kwargs.get("max_tokens", 2048),
                temperature=kwargs.get("temperature", 0.7)
            )
            
            if response.status_code == 200:
                return response.output.text
            else:
                return f"通义灵码错误: {response.message}"
        except Exception as e:
            self.logger.error(f"通义灵码API调用失败: {str(e)}")
            return f"通义灵码错误: {str(e)}"
    
    async def chat_complete(self, messages: List[Dict], **kwargs) -> str:
        try:
            import dashscope
            dashscope.api_key = self.api_key
            
            from dashscope import Generation
            # 转换消息格式
            tongyi_messages = []
            for msg in messages:
                tongyi_messages.append({
                    "role": "user" if msg["role"] == "user" else "assistant",
                    "content": msg["content"]
                })
            
            response = Generation.call(
                model="qwen-plus",
                messages=tongyi_messages,
                max_tokens=kwargs.get("max_tokens", 2048),
                temperature=kwargs.get("temperature", 0.7)
            )
            
            if response.status_code == 200:
                return response.output.choices[0].message.content
            else:
                return f"通义灵码错误: {response.message}"
        except Exception as e:
            self.logger.error(f"通义灵码聊天失败: {str(e)}")
            return f"通义灵码错误: {str(e)}"
    
    def get_cost_estimate(self, prompt_tokens: int, completion_tokens: int) -> float:
        # 通义灵码有免费额度
        return 0.0

class MultiLLMService:
    """多模型LLM服务"""
    
    def __init__(self):
        self.adapters = {}
        self.logger = logging.getLogger("MultiLLMService")
        self._initialize_adapters()
    
    def _initialize_adapters(self):
        """初始化所有适配器"""
        # DeepSeek（免费主力）
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            self.adapters[LLMProvider.DEEPSEEK] = DeepSeekAdapter(deepseek_key)
        
        # OpenAI（GitHub Copilot备选）
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.adapters[LLMProvider.OPENAI] = OpenAIAdapter(
                openai_key, 
                os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            )
        
        # 通义灵码
        tongyi_key = os.getenv("TONGYI_API_KEY")
        if tongyi_key:
            self.adapters[LLMProvider.TONGYI] = TongyiAdapter(tongyi_key)
    
    def get_available_providers(self) -> List[LLMProvider]:
        """获取可用的模型提供商"""
        return list(self.adapters.keys())
    
    async def generate_with_fallback(self, prompt: str, preferred_provider: LLMProvider = None, **kwargs) -> Dict[str, Any]:
        """使用回退策略生成代码"""
        providers_order = self._get_providers_order(preferred_provider)
        if not providers_order:
            return {
                "success": False,
                "error": "未配置任何模型API key，请在环境变量中设置 DEEPSEEK_API_KEY、OPENAI_API_KEY 或 TONGYI_API_KEY。",
                "content": "未找到可用模型供应商"
            }
        for provider in providers_order:
            if provider in self.adapters:
                try:
                    self.logger.info(f"尝试使用 {provider.value} 生成代码")
                    result = await self.adapters[provider].generate_code(prompt, **kwargs)
                    # 检查是否是错误消息
                    is_error = (
                        result is None or
                        result.startswith("DeepSeek错误") or 
                        result.startswith("OpenAI错误") or 
                        result.startswith("通义灵码错误") or
                        "错误:" in result[:50]
                    )
                    if not is_error:
                        return {
                            "success": True,
                            "content": result,
                            "provider": provider.value,
                            "cost_estimate": 0.0
                        }
                    else:
                        self.logger.warning(f"{provider.value} 返回错误: {result}")
                        continue
                except Exception as e:
                    self.logger.warning(f"{provider.value} 生成失败: {str(e)}")
                    continue
        return {
            "success": False,
            "error": "所有模型供应商都失败了，请检查API key配置或网络连接。",
            "content": "无法生成代码修复方案"
        }
    
    async def chat_complete_with_fallback(self, messages: List[Dict], preferred_provider: LLMProvider = None, **kwargs) -> Dict[str, Any]:
        """使用回退策略进行聊天补全"""
        providers_order = self._get_providers_order(preferred_provider)
        
        for provider in providers_order:
            if provider in self.adapters:
                try:
                    self.logger.info(f"尝试使用 {provider.value} 进行聊天补全")
                    result = await self.adapters[provider].chat_complete(messages, **kwargs)
                    
                    # 检查是否是错误消息
                    is_error = (
                        result.startswith("DeepSeek错误") or 
                        result.startswith("OpenAI错误") or 
                        result.startswith("通义灵码错误") or
                        "错误:" in result[:50]  # 前50个字符中包含错误信息
                    )
                    
                    if not is_error:
                        return {
                            "success": True,
                            "content": result,
                            "provider": provider.value
                        }
                    else:
                        self.logger.warning(f"{provider.value} 返回错误: {result}")
                        continue
                    
                except Exception as e:
                    self.logger.warning(f"{provider.value} 聊天失败: {str(e)}")
                    continue
        
        return {
            "success": False,
            "error": "所有模型提供商都失败了",
            "content": "无法完成对话"
        }
    
    def _get_providers_order(self, preferred_provider: LLMProvider = None) -> List[LLMProvider]:
        """获取提供商优先级顺序"""
        if preferred_provider and preferred_provider in self.adapters:
            # 优先使用指定提供商，然后是其他可用提供商
            other_providers = [p for p in self.adapters.keys() if p != preferred_provider]
            return [preferred_provider] + other_providers
        else:
            # 默认优先级：DeepSeek > 通义灵码 > OpenAI
            priority_order = [LLMProvider.DEEPSEEK, LLMProvider.TONGYI, LLMProvider.OPENAI]
            available = [p for p in priority_order if p in self.adapters]
            return available