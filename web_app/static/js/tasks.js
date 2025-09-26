// [file name]: web_app/static/js/tasks.js
// [file content begin]
let ws;
let allTasks = [];

function initTasksPage() {
    connectWebSocket();
    loadTasks();
    // 每10秒刷新一次任务列表
    setInterval(loadTasks, 10000);
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('WebSocket连接已建立');
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    ws.onclose = () => {
        console.log('WebSocket连接已关闭，5秒后重连...');
        setTimeout(connectWebSocket, 5000);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket错误:', error);
    };
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'progress_update':
        case 'task_completed':
            loadTasks(); // 重新加载任务列表
            break;
    }
}

async function loadTasks() {
    try {
        const response = await fetch('/api/tasks');
        const data = await response.json();
        allTasks = data.tasks;
        updateTaskStatistics();
        renderTasksList();
    } catch (error) {
        console.error('加载任务列表失败:', error);
    }
}

function updateTaskStatistics() {
    const stats = {
        total: allTasks.length,
        completed: allTasks.filter(t => t.status === 'completed').length,
        running: allTasks.filter(t => t.status === 'running').length,
        failed: allTasks.filter(t => t.status === 'failed').length
    };
    
    document.getElementById('totalTasksCount').textContent = stats.total;
    document.getElementById('completedTasksCount').textContent = stats.completed;
    document.getElementById('runningTasksCount').textContent = stats.running;
    document.getElementById('failedTasksCount').textContent = stats.failed;
}

function renderTasksList() {
    const tasksList = document.getElementById('tasksList');
    const statusFilter = document.getElementById('statusFilter').value;
    
    let filteredTasks = allTasks;
    if (statusFilter) {
        filteredTasks = allTasks.filter(t => t.status === statusFilter);
    }
    
    if (filteredTasks.length === 0) {
        tasksList.innerHTML = `
            <div class="text-center py-4">
                <i class="fas fa-inbox fa-2x text-muted"></i>
                <p class="mt-2 text-muted">暂无任务</p>
            </div>
        `;
        return;
    }
    
    // 按创建时间排序
    filteredTasks.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    
    const html = filteredTasks.map(task => createTaskCard(task)).join('');
    tasksList.innerHTML = html;
}

function createTaskCard(task) {
    const statusBadge = getStatusBadge(task.status);
    const progress = task.progress || 0;
    const completedAt = task.completed_at ? new Date(task.completed_at).toLocaleString() : '-';
    const defectsFound = task.results?.defects_found || 0;
    
    return `
        <div class="card task-card mb-3" style="transition: all 0.2s;">
            <div class="card-body">
                <div class="row align-items-center">
                    <div class="col-md-2">
                        <h6 class="card-title mb-1">${task.id}</h6>
                        <small class="text-muted">${new Date(task.created_at).toLocaleString()}</small>
                    </div>
                    <div class="col-md-3">
                        <div class="small text-muted">代码库路径:</div>
                        <div class="text-truncate" title="${task.repo_path}">${task.repo_path}</div>
                    </div>
                    <div class="col-md-2">
                        <div class="small text-muted">模型:</div>
                        <div>${task.preferred_model}</div>
                    </div>
                    <div class="col-md-1">
                        <div class="small text-muted">问题数:</div>
                        <div class="fw-bold ${defectsFound > 0 ? 'text-warning' : 'text-success'}">${defectsFound}</div>
                    </div>
                    <div class="col-md-2">
                        <div class="mb-1">${statusBadge}</div>
                        <div class="progress progress-sm">
                            <div class="progress-bar ${getProgressBarClass(task.status)}" 
                                 style="width: ${progress}%"></div>
                        </div>
                        <small class="text-muted">${progress}%</small>
                    </div>
                    <div class="col-md-2 text-end">
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-primary" onclick="viewTaskDetail('${task.id}')" 
                                    title="查看详情">
                                <i class="fas fa-eye"></i>
                            </button>
                            ${task.status === 'completed' && task.results ? 
                                `<button class="btn btn-outline-success" onclick="downloadReport('${task.id}')" 
                                         title="下载报告">
                                    <i class="fas fa-download"></i>
                                </button>` : ''}
                            <button class="btn btn-outline-danger" onclick="deleteTask('${task.id}')" 
                                    title="删除任务">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                </div>
                ${task.current_step ? 
                    `<div class="row mt-2">
                        <div class="col-12">
                            <small class="text-muted">当前步骤: ${task.current_step}</small>
                        </div>
                    </div>` : ''}
            </div>
        </div>
    `;
}

function getStatusBadge(status) {
    const badges = {
        'completed': '<span class="badge bg-success task-status-badge">已完成</span>',
        'failed': '<span class="badge bg-danger task-status-badge">失败</span>',
        'running': '<span class="badge bg-warning task-status-badge">运行中</span>',
        'pending': '<span class="badge bg-secondary task-status-badge">等待中</span>'
    };
    return badges[status] || `<span class="badge bg-secondary task-status-badge">${status}</span>`;
}

function getProgressBarClass(status) {
    const classes = {
        'completed': 'bg-success',
        'failed': 'bg-danger',
        'running': 'bg-warning',
        'pending': 'bg-secondary'
    };
    return classes[status] || 'bg-secondary';
}

function filterTasks() {
    renderTasksList();
}

async function createTask() {
    const repoPath = document.getElementById('taskRepoPath').value;
    const model = document.getElementById('taskModel').value;
    
    if (!repoPath) {
        alert('请输入代码库路径');
        return;
    }
    
    try {
        const response = await fetch('/api/tasks/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                repo_path: repoPath,
                preferred_model: model
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            // 关闭模态框
            const modal = bootstrap.Modal.getInstance(document.getElementById('newTaskModal'));
            modal.hide();
            
            // 清空表单
            document.getElementById('newTaskForm').reset();
            
            // 刷新任务列表
            loadTasks();
            
            // 显示成功消息
            showToast('success', '任务创建成功', `任务ID: ${result.task_id}`);
        } else {
            showToast('error', '创建任务失败', result.detail || '未知错误');
        }
    } catch (error) {
        console.error('创建任务失败:', error);
        showToast('error', '创建任务失败', error.message);
    }
}

function viewTaskDetail(taskId) {
    window.location.href = `/tasks/${taskId}`;
}

async function downloadReport(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/report`);
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `report_${taskId}.md`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            showToast('success', '报告下载成功', '');
        } else {
            showToast('error', '下载报告失败', '');
        }
    } catch (error) {
        console.error('下载报告失败:', error);
        showToast('error', '下载报告失败', error.message);
    }
}

async function deleteTask(taskId) {
    if (!confirm('确定要删除这个任务吗？')) {
        return;
    }
    
    // 这里应该调用删除API，目前只是从前端移除
    showToast('info', '删除功能', '删除功能暂未实现');
}

function showToast(type, title, message) {
    // 简单的提示信息，可以用更好的toast库替换
    const alertClass = {
        'success': 'alert-success',
        'error': 'alert-danger',
        'info': 'alert-info',
        'warning': 'alert-warning'
    };
    
    const toast = document.createElement('div');
    toast.className = `alert ${alertClass[type]} alert-dismissible fade show position-fixed`;
    toast.style = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    toast.innerHTML = `
        <strong>${title}</strong>
        ${message ? `<div>${message}</div>` : ''}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(toast);
    
    // 3秒后自动移除
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 3000);
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', initTasksPage);
// [file content end]