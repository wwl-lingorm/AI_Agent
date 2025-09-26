# [file name]: web_app/main.py
# [file content begin]
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, Response
from fastapi.requests import Request
import uvicorn
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import logging
from .report_generator import ReportGenerator
from pydantic import BaseModel
from fastapi import Body
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

    def add_report_route(self):
        generator = ReportGenerator()
        @self.app.get("/api/tasks/{task_id}/report")
        async def download_report(task_id: str, fmt: str = "md"):
            """生成并下载检测报告，支持md/html/pdf"""
            if task_id not in self.tasks:
                raise HTTPException(status_code=404, detail="任务不存在")
            task = self.tasks[task_id]
            # 构造context
            context = self._build_report_context(task)
            if not context or not context.get("filename"):
                return Response(content="报告生成失败：context数据为空或无效。请检查任务数据是否完整。", media_type="text/plain")
            try:
                if fmt == "md":
                    content = generator.render_markdown(context)
                    filename = f"report_{task_id}.md"
                    media_type = "text/markdown"
                elif fmt == "html":
                    content = generator.render_html(context)
                    filename = f"report_{task_id}.html"
                    media_type = "text/html"
                elif fmt == "pdf":
                    content = generator.render_pdf(context)
                    filename = f"report_{task_id}.pdf"
                    media_type = "application/pdf"
                else:
                    raise HTTPException(status_code=400, detail="不支持的报告格式")
            except Exception as e:
                return Response(content=f"报告渲染异常：{str(e)}", media_type="text/plain")
            headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
            return Response(content=content, media_type=media_type, headers=headers)

    def _build_report_context(self, task):
        """将task结构转为报告模板context，自动兼容多种结构"""
        results = task.get('results', {})
        issues = []
        # 1. 兼容subtask_results下各种命名
        for agent, agent_result in (results.get('subtask_results', {}) or {}).items():
            if isinstance(agent_result, dict):
                for key in ['issues', 'defects', 'problems']:
                    if key in agent_result and isinstance(agent_result[key], list):
                        for issue in agent_result[key]:
                            issues.append(issue)
        # 2. 兼容直接有issues/defects/problems的情况
        for key in ['issues', 'defects', 'problems']:
            if not issues and key in results and isinstance(results[key], list):
                issues = results[key]
        # 3. 兼容单个问题对象
        if not issues and isinstance(results, dict):
            for v in results.values():
                if isinstance(v, list) and v and isinstance(v[0], dict) and 'message' in v[0]:
                    issues = v
        # 4. 代码前后对比
        code_before = results.get('code_before', '')
        code_after = results.get('code_after', '')
        # 兼容部分agent直接输出修复建议
        if not code_after:
            for agent, agent_result in (results.get('subtask_results', {}) or {}).items():
                if isinstance(agent_result, dict):
                    for k in ['fix_suggestion', 'fixed_code', 'code_after']:
                        if k in agent_result and isinstance(agent_result[k], str) and len(agent_result[k]) > 10:
                            code_after = agent_result[k]
        # 统计
        total_issues = len(issues)
        fixed_issues = sum(1 for i in issues if i.get('fixed', True))
        success_rate = int(fixed_issues / total_issues * 100) if total_issues else 100
        # 构造context
        context = {
            "filename": task.get('repo_path', ''),
            "date": task.get('completed_at', task.get('created_at', '')),
            "tools": results.get('tools', ['pylint','mypy','bandit']),
            "model": results.get('model_selected', task.get('preferred_model','')),
            "total_issues": total_issues,
            "fixed_issues": fixed_issues,
            "success_rate": success_rate,
            "issues": issues,
            "code_before": code_before,
            "code_after": code_after
        }
        return context

    # _generate_report_markdown 已被ReportGenerator替代
    def __init__(self):
        self.app = FastAPI(
            title="多Agent缺陷检测系统",
            description="基于AI的智能代码缺陷检测与修复平台",
            version="1.0.0"
        )
        self.manager = ConnectionManager()
        self.tasks = {}  # 存储任务状态
        self.system = None
        # 设置模板和静态文件
        self.templates = Jinja2Templates(directory="web_app/templates")
        self._setup_routes()
        self.add_report_route()
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

        @self.app.get("/tasks", response_class=HTMLResponse)
        async def tasks_page(request: Request):
            return self.templates.TemplateResponse("tasks.html", {"request": request})

        @self.app.get("/models", response_class=HTMLResponse)
        async def models_page(request: Request):
            return self.templates.TemplateResponse("models.html", {"request": request})

        @self.app.get("/settings", response_class=HTMLResponse)
        async def settings_page(request: Request):
            return self.templates.TemplateResponse("settings.html", {"request": request})

        @self.app.get("/tasks/{task_id}", response_class=HTMLResponse)
        async def task_detail_page(request: Request, task_id: str):
            return self.templates.TemplateResponse("task_detail.html", {"request": request})
        
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

        class AnalysisTaskRequest(BaseModel):
            repo_path: str
            preferred_model: Optional[str] = "deepseek"

        @self.app.post("/api/tasks/analyze")
        async def create_analysis_task(request: AnalysisTaskRequest = Body(...)):
            """创建代码分析任务，支持目录或单文件"""
            try:
                repo_path = request.repo_path.strip()
                preferred_model = request.preferred_model
                task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # 验证路径
                if not os.path.exists(repo_path):
                    raise HTTPException(status_code=400, detail=f"路径不存在: {repo_path}")
                
                if not (os.path.isdir(repo_path) or (os.path.isfile(repo_path) and repo_path.endswith('.py'))):
                    raise HTTPException(status_code=400, detail="只支持目录或Python文件")
                
                # 创建任务记录
                task_data = {
                    "id": task_id,
                    "repo_path": repo_path,
                    "preferred_model": preferred_model,
                    "status": "running",
                    "progress": 0,
                    "current_stage": "初始化...",
                    "created_at": datetime.now().isoformat(),
                    "results": {}
                }
                self.tasks[task_id] = task_data
                
                # 立即推送任务创建成功
                await self.manager.broadcast(json.dumps({
                    "type": "task_created",
                    "task_id": task_id,
                    "message": "任务已创建，开始分析..."
                }))
                
                # 启动异步任务
                asyncio.create_task(self._execute_analysis_task(task_id, repo_path, preferred_model))
                
                return {"task_id": task_id, "status": "created", "message": "任务已创建"}
                
            except Exception as e:
                logger.error(f"创建任务失败: {str(e)}")
                raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")
        
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

    async def _execute_analysis_task(self, task_id: str, repo_path: str, preferred_model: str):
        """执行分析任务并推送进度"""
        try:
            # 创建进度回调函数
            async def progress_callback(progress: int, stage: str):
                await self._update_task_progress(task_id, progress, stage)
            
            # 更新任务状态
            await self._update_task_progress(task_id, 5, "正在初始化Agent...")
            
            # 执行协调器任务（传递进度回调）
            result = await self.coordinator.execute({
                "type": "defect_analysis",
                "description": f"分析代码库 {repo_path} 的缺陷",
                "repo_path": repo_path,
                "preferred_model": preferred_model
            }, progress_callback)
            
            # 任务完成
            self.tasks[task_id].update({
                "status": "completed",
                "progress": 100,
                "current_stage": "分析完成",
                "completed_at": datetime.now().isoformat(),
                "results": result
            })
            
            await self.manager.broadcast(json.dumps({
                "type": "task_completed",
                "task_id": task_id,
                "progress": 100,
                "message": "分析完成"
            }))
            
        except Exception as e:
            logger.error(f"任务执行失败 {task_id}: {str(e)}")
            self.tasks[task_id].update({
                "status": "failed",
                "progress": 0,
                "current_stage": "执行失败",
                "error": str(e)
            })
            
            await self.manager.broadcast(json.dumps({
                "type": "task_failed",
                "task_id": task_id,
                "error": str(e)
            }))
    
    async def _run_analysis_task(self, task_id: str):
        """向后兼容的方法，重定向到新方法"""
        task = self.tasks.get(task_id)
        if task:
            await self._execute_analysis_task(task_id, task["repo_path"], task["preferred_model"])

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