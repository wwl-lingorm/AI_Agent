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
        
        // 每10秒刷新一次状态
        setInterval(() => this.loadSystemStatus(), 10000);
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
        console.log('收到WebSocket消息:', data);
        switch (data.type) {
            case 'task_progress':
                this.updateTaskProgress(data.task_id, data.progress, data.message);
                break;
            case 'task_completed':
                this.handleTaskCompleted(data);
                break;
            case 'task_failed':
                this.handleTaskFailed(data);
                break;
        }
    }

    updateTaskProgress(taskId, progress, message) {
        console.log(`任务 ${taskId} 进度更新: ${progress}% - ${message}`);
        
        // 更新页面上的进度条
        const taskCards = document.querySelectorAll('.task-item');
        taskCards.forEach(card => {
            const title = card.querySelector('.card-title');
            if (title && title.textContent.includes(taskId)) {
                const progressBar = card.querySelector('.progress-bar');
                const progressText = card.querySelector('.text-muted');
                
                if (progressBar) {
                    progressBar.style.width = `${progress}%`;
                }
                if (progressText) {
                    progressText.textContent = `${progress}%`;
                }
                
                // 更新状态信息
                if (message) {
                    const statusElement = card.querySelector('.small.text-muted');
                    if (statusElement) {
                        statusElement.textContent = message;
                    }
                }
            }
        });
        
        // 如果有详情页面打开，也更新详情页面的进度
        if (this.currentTaskId === taskId) {
            this.updateTaskDetailsProgress(taskId, progress, message);
        }
    }

    updateTaskDetailsProgress(taskId, progress, message) {
        // 更新详情页面的进度显示
        const detailProgress = document.getElementById('taskDetailProgress');
        const detailProgressText = document.getElementById('taskDetailProgressText');
        
        if (detailProgress) {
            detailProgress.style.width = `${progress}%`;
        }
        if (detailProgressText) {
            detailProgressText.textContent = `${progress}%`;
        }
        
        // 添加进度日志
        const logContainer = document.getElementById('taskLogs');
        if (logContainer && message) {
            const logEntry = document.createElement('div');
            logEntry.className = 'log-entry small text-muted mb-1';
            logEntry.innerHTML = `<i class="fas fa-clock"></i> ${new Date().toLocaleTimeString()} - ${message}`;
            logContainer.appendChild(logEntry);
            logContainer.scrollTop = logContainer.scrollHeight;
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
        // 分析表单提交（彻底优化：只要上传就分析，无需路径弹窗）
        document.getElementById('analysisForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const repoUpload = document.getElementById('repoUpload');
            const repoPathInput = document.getElementById('repoPath');
            const repoPath = repoPathInput.value.trim();
            let path = repoPath;
            const progressModal = new bootstrap.Modal(document.getElementById('progressModal'));
            document.getElementById('progressText').textContent = '初始化...';
            document.getElementById('progressPercent').textContent = '0%';
            document.getElementById('progressBar').style.width = '0%';
            document.getElementById('progressDetails').textContent = '';
            progressModal.show();


            // 优先处理上传
            if (repoUpload.files && repoUpload.files.length > 0) {
                const formData = new FormData();
                for (let i = 0; i < repoUpload.files.length; i++) {
                    formData.append('files', repoUpload.files[i]);
                }
                try {
                    const uploadResp = await fetch('/api/langchain/upload', {
                        method: 'POST',
                        body: formData
                    });
                    const uploadData = await uploadResp.json();
                    if (!uploadData.temp_dir) throw new Error('上传失败');
                    path = uploadData.temp_dir;
                } catch (err) {
                    document.getElementById('progressText').textContent = '上传失败';
                    document.getElementById('progressDetails').textContent = err.message;
                    return;
                }
            }

            // 未上传且未填写路径，弹窗提示
            if (!(repoUpload.files && repoUpload.files.length > 0) && !path) {
                progressModal.hide();
                alert('请上传文件或填写代码库路径');
                return;
            }

            // 路径输入但不存在，弹窗提示（前端简单校验，后端仍需兜底）
            if (path && !(repoUpload.files && repoUpload.files.length > 0)) {
                // 仅在本地环境可用，简单判断路径格式
                if (!/^([a-zA-Z]:\\|\/|\.\/|\.\\)/.test(path)) {
                    progressModal.hide();
                    alert('请输入有效的本地路径，如 C:/project 或 ./src');
                    return;
                }
            }

            // 调用LangChain流水线API
            try {
                const resp = await fetch('/api/langchain/pipeline', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ repo_path: path })
                });
                const data = await resp.json();
                document.getElementById('progressText').textContent = '分析完成';
                document.getElementById('progressPercent').textContent = '100%';
                document.getElementById('progressBar').style.width = '100%';
                document.getElementById('progressDetails').textContent = '结果已生成，可在任务详情页查看';
                setTimeout(() => progressModal.hide(), 2000);
            } catch (err) {
                document.getElementById('progressText').textContent = '分析失败';
                document.getElementById('progressDetails').textContent = err.message;
            }
        });

        // 刷新按钮
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.loadSystemStatus();
            this.loadTasks();
        });
    }

    async startAnalysis() {
        const repoUpload = document.getElementById('repoUpload');
        const repoPathInput = document.getElementById('repoPath');
        const repoPath = repoPathInput.value.trim();
        let path = repoPath;
        const model = document.getElementById('modelSelect').value;
        const analyzeBtn = document.getElementById('analyzeBtn');
        analyzeBtn.disabled = true;
        analyzeBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>分析中...';
        // 优先处理上传
        if (repoUpload.files && repoUpload.files.length > 0) {
            const formData = new FormData();
            for (let i = 0; i < repoUpload.files.length; i++) {
                formData.append('files', repoUpload.files[i]);
            }
            try {
                const uploadResp = await fetch('/api/langchain/upload', {
                    method: 'POST',
                    body: formData
                });
                const uploadData = await uploadResp.json();
                if (!uploadData.temp_dir) throw new Error('上传失败');
                path = uploadData.temp_dir;
            } catch (err) {
                alert('上传失败: ' + err.message);
                analyzeBtn.disabled = false;
                analyzeBtn.innerHTML = '<i class="fas fa-play me-2"></i>开始分析';
                return;
            }
        }
        // 只要上传了文件/文件夹，path为空也允许分析
        if (!path && repoUpload.files && repoUpload.files.length > 0) {
            path = undefined; // 传给后端的repo_path为undefined或空字符串，后端用上传目录
        }
        try {
            const resp = await fetch('/api/langchain/pipeline', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ repo_path: path, preferred_model: model })
            });
            const data = await resp.json();
            alert('分析完成！结果已生成，可在任务详情页查看');
        } catch (error) {
            alert('分析请求失败: ' + error.message);
        }
        analyzeBtn.disabled = false;
        analyzeBtn.innerHTML = '<i class="fas fa-play me-2"></i>开始分析';
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