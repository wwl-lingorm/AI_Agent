# [file name]: web_app/main.py
# [file content begin]
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.requests import Request
import uvicorn
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import logging

from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.analysis_agent import AnalysisAgent
from src.agents.detection_agent import DetectionAgent
from src.agents.repair_agent import RepairAgent
from src.agents.validation_agent import ValidationAgent
from src.utils.multi_llm_service import MultiLLMService
from src.utils.model_selector import ModelSelector

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WebInterface")

class ConnectionManager:
    """管理WebSocket连接"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"广播消息失败: {e}")

class WebInterface:
    def __init__(self):
        self.app = FastAPI(
            title="多Agent缺陷检测系统",
            description="基于AI的智能代码缺陷检测与修复平台",
            version="1.0.0"
        )
        self.manager = ConnectionManager()
        self.tasks: Dict[str, Dict] = {}  # 存储任务状态
        self.system = None
        
        # 设置模板和静态文件
        self.templates = Jinja2Templates(directory="web_app/templates")
        
        self._setup_routes()
        self._initialize_system()

    def _initialize_system(self):
        """初始化多Agent系统"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            self.llm_service = MultiLLMService()
            self.model_selector = ModelSelector()
            
            # 初始化Agent
            self.coordinator = CoordinatorAgent(self.model_selector)
            self.analysis_agent = AnalysisAgent()
            self.detection_agent = DetectionAgent()
            self.repair_agent = RepairAgent(self.llm_service)
            self.validation_agent = ValidationAgent()
            
            # 注册Agent
            self.coordinator.register_agent("AnalysisAgent", self.analysis_agent)
            self.coordinator.register_agent("DetectionAgent", self.detection_agent)
            self.coordinator.register_agent("RepairAgent", self.repair_agent)
            self.coordinator.register_agent("ValidationAgent", self.validation_agent)
            
            logger.info("多Agent系统初始化完成")
        except Exception as e:
            logger.error(f"系统初始化失败: {e}")

    def _setup_routes(self):
        """设置路由"""
        
        # 挂载静态文件
        self.app.mount("/static", StaticFiles(directory="web_app/static"), name="static")
        
        @self.app.get("/", response_class=HTMLResponse)
        async def read_root(request: Request):
            return self.templates.TemplateResponse("index.html", {"request": request})
        
        @self.app.get("/dashboard")
        async def dashboard(request: Request):
            return self.templates.TemplateResponse("dashboard.html", {"request": request})
        
        @self.app.get("/api/system/status")
        async def get_system_status():
            """获取系统状态"""
            status = {
                "status": "running",
                "agents_initialized": self.system is not None,
                "available_models": [p.value for p in self.llm_service.get_available_providers()] if hasattr(self, 'llm_service') else [],
                "active_tasks": len([t for t in self.tasks.values() if t['status'] in ['running', 'pending']]),
                "total_tasks": len(self.tasks)
            }
            return status
        
        @self.app.post("/api/tasks/analyze")
        async def create_analysis_task(repo_path: str, preferred_model: Optional[str] = "deepseek"):
            """创建代码分析任务"""
            task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if not os.path.exists(repo_path):
                raise HTTPException(status_code=400, detail="代码库路径不存在")
            
            self.tasks[task_id] = {
                "id": task_id,
                "repo_path": repo_path,
                "preferred_model": preferred_model,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "progress": 0,
                "results": None
            }
            
            # 在后台运行任务
            asyncio.create_task(self._run_analysis_task(task_id))
            
            return {"task_id": task_id, "status": "created"}
        
        @self.app.get("/api/tasks/{task_id}")
        async def get_task_status(task_id: str):
            """获取任务状态"""
            if task_id not in self.tasks:
                raise HTTPException(status_code=404, detail="任务不存在")
            return self.tasks[task_id]
        
        @self.app.get("/api/tasks")
        async def get_all_tasks():
            """获取所有任务"""
            return {
                "tasks": list(self.tasks.values()),
                "total": len(self.tasks)
            }
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket端点用于实时更新"""
            await self.manager.connect(websocket)
            try:
                while True:
                    # 保持连接活跃
                    await websocket.receive_text()
            except WebSocketDisconnect:
                self.manager.disconnect(websocket)

    async def _run_analysis_task(self, task_id: str):
        """在后台运行分析任务"""
        task = self.tasks[task_id]
        
        try:
            # 更新任务状态
            task["status"] = "running"
            await self._update_task_progress(task_id, 10, "开始代码分析...")
            
            # 运行分析
            result = await self.coordinator.execute({
                "type": "defect_analysis",
                "description": f"分析代码库 {task['repo_path']} 的缺陷",
                "repo_path": task["repo_path"],
                "preferred_model": task["preferred_model"]
            })
            
            await self._update_task_progress(task_id, 80, "分析完成，生成报告...")
            
            # 保存结果
            task["results"] = result
            task["status"] = "completed"
            task["completed_at"] = datetime.now().isoformat()
            await self._update_task_progress(task_id, 100, "任务完成")
            
            # 广播任务完成
            await self.manager.broadcast(json.dumps({
                "type": "task_completed",
                "task_id": task_id,
                "results": result
            }))
            
        except Exception as e:
            logger.error(f"任务 {task_id} 执行失败: {e}")
            task["status"] = "failed"
            task["error"] = str(e)
            await self._update_task_progress(task_id, 0, f"任务失败: {str(e)}")

    async def _update_task_progress(self, task_id: str, progress: int, message: str):
        """更新任务进度"""
        if task_id in self.tasks:
            self.tasks[task_id]["progress"] = progress
            self.tasks[task_id]["current_step"] = message
            
            # 通过WebSocket广播进度更新
            await self.manager.broadcast(json.dumps({
                "type": "progress_update",
                "task_id": task_id,
                "progress": progress,
                "message": message
            }))

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """运行Web服务器"""
        uvicorn.run(self.app, host=host, port=port)

# 创建应用实例
web_interface = WebInterface()
app = web_interface.app

if __name__ == "__main__":
    web_interface.run()
# [file content end]