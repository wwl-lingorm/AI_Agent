// [file name]: web_app/static/js/dashboard.js
// [file content begin]
class Dashboard {
    constructor() {
        this.ws = null;
        this.currentTaskId = null;
        this.init();
    }

    init() {
        this.connectWebSocket();
        this.loadSystemStatus();
        this.loadTasks();
        this.setupEventListeners();
        
        // 每30秒刷新一次状态
        setInterval(() => this.loadSystemStatus(), 30000);
        setInterval(() => this.loadTasks(), 10000);
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket连接已建立');
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket连接已关闭，5秒后重连...');
            setTimeout(() => this.connectWebSocket(), 5000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket错误:', error);
        };
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'progress_update':
                this.updateProgress(data);
                break;
            case 'task_completed':
                this.handleTaskCompleted(data);
                break;
        }
    }

    async loadSystemStatus() {
        try {
            const response = await fetch('/api/system/status');
            const status = await response.json();
            this.updateStatusDisplay(status);
        } catch (error) {
            console.error('加载系统状态失败:', error);
        }
    }

    updateStatusDisplay(status) {
        document.getElementById('modelCount').textContent = status.available_models.length;
        document.getElementById('activeTasks').textContent = status.active_tasks;
        document.getElementById('totalTasks').textContent = status.total_tasks;
        document.getElementById('systemStatus').textContent = status.status === 'running' ? '运行中' : '异常';
    }

    async loadTasks() {
        try {
            const response = await fetch('/api/tasks');
            const data = await response.json();
            this.renderTaskList(data.tasks);
        } catch (error) {
            console.error('加载任务列表失败:', error);
        }
    }

    renderTaskList(tasks) {
        const taskList = document.getElementById('taskList');
        
        if (tasks.length === 0) {
            taskList.innerHTML = `
                <div class="text-center py-4">
                    <i class="fas fa-inbox fa-2x text-muted"></i>
                    <p class="mt-2 text-muted">暂无任务</p>
                </div>
            `;
            return;
        }

        // 按创建时间排序，最新的在前
        tasks.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        
        const html = tasks.map(task => this.createTaskItem(task)).join('');
        taskList.innerHTML = html;
    }

    createTaskItem(task) {
        const statusClass = this.getStatusClass(task.status);
        const statusText = this.getStatusText(task.status);
        const progress = task.progress || 0;
        
        return `
            <div class="card task-item ${statusClass} mb-3">
                <div class="card-body">
                    <div class="row align-items-center">
                        <div class="col-md-3">
                            <h6 class="card-title mb-1">${task.id}</h6>
                            <small class="text-muted">${new Date(task.created_at).toLocaleString()}</small>
                        </div>
                        <div class="col-md-3">
                            <div class="small">代码库:</div>
                            <div class="text-truncate">${task.repo_path}</div>
                        </div>
                        <div class="col-md-2">
                            <span class="badge bg-${this.getStatusColor(task.status)}">${statusText}</span>
                        </div>
                        <div class="col-md-2">
                            <div class="progress" style="height: 6px;">
                                <div class="progress-bar" style="width: ${progress}%"></div>
                            </div>
                            <small class="text-muted">${progress}%</small>
                        </div>
                        <div class="col-md-2 text-end">
                            <button class="btn btn-sm btn-outline-primary" onclick="dashboard.viewTaskDetails('${task.id}')">
                                <i class="fas fa-eye"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    getStatusClass(status) {
        const statusMap = {
            'completed': 'status-completed',
            'failed': 'status-failed',
            'running': 'status-running'
        };
        return statusMap[status] || '';
    }

    getStatusColor(status) {
        const colorMap = {
            'completed': 'success',
            'failed': 'danger',
            'running': 'warning',
            'pending': 'secondary'
        };
        return colorMap[status] || 'secondary';
    }

    getStatusText(status) {
        const textMap = {
            'completed': '已完成',
            'failed': '失败',
            'running': '运行中',
            'pending': '等待中'
        };
        return textMap[status] || status;
    }

    setupEventListeners() {
        // 分析表单提交
        document.getElementById('analysisForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startAnalysis();
        });

        // 刷新按钮
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.loadSystemStatus();
            this.loadTasks();
        });
    }

    async startAnalysis() {
        const repoPath = document.getElementById('repoPath').value;
        const model = document.getElementById('modelSelect').value;

        if (!repoPath) {
            alert('请输入代码库路径');
            return;
        }

        const analyzeBtn = document.getElementById('analyzeBtn');
        analyzeBtn.disabled = true;
        analyzeBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>分析中...';

        try {
            const response = await fetch('/api/tasks/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `repo_path=${encodeURIComponent(repoPath)}&preferred_model=${model}`
            });

            const result = await response.json();
            
            if (response.ok) {
                this.currentTaskId = result.task_id;
                this.showProgressModal();
                this.loadTasks(); // 刷新任务列表
            } else {
                alert('创建任务失败: ' + result.detail);
            }
        } catch (error) {
            console.error('分析请求失败:', error);
            alert('分析请求失败: ' + error.message);
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.innerHTML = '<i class="fas fa-play me-2"></i>开始分析';
        }
    }

    showProgressModal() {
        const modal = new bootstrap.Modal(document.getElementById('progressModal'));
        modal.show();
    }

    updateProgress(data) {
        if (data.task_id === this.currentTaskId) {
            const progressBar = document.getElementById('progressBar');
            const progressPercent = document.getElementById('progressPercent');
            const progressText = document.getElementById('progressText');
            const progressDetails = document.getElementById('progressDetails');
            
            progressBar.style.width = `${data.progress}%`;
            progressPercent.textContent = `${data.progress}%`;
            progressText.textContent = data.message;
            progressDetails.innerHTML = `任务ID: ${data.task_id}`;
        }
    }

    handleTaskCompleted(data) {
        if (data.task_id === this.currentTaskId) {
            setTimeout(() => {
                const modal = bootstrap.Modal.getInstance(document.getElementById('progressModal'));
                if (modal) modal.hide();
                
                this.showResults(data.results);
                this.currentTaskId = null;
            }, 2000);
        }
    }

    showResults(results) {
        // 这里可以显示详细的分析结果
        alert(`分析完成！发现 ${results.defects_found || 0} 个问题。`);
    }

    viewTaskDetails(taskId) {
        // 跳转到任务详情页面或显示模态框
        window.location.href = `/tasks/${taskId}`;
    }
}

// 初始化仪表板
const dashboard = new Dashboard();
// [file content end]