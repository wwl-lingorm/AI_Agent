from abc import ABC, abstractmethod
from typing import Dict, Any, List
import logging

class BaseAgent(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"agent.{name}")
    
    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务的核心方法"""
        pass
    
    def log(self, message: str, level: str = "info"):
        """统一的日志记录"""
        getattr(self.logger, level)(f"{self.name}: {message}")