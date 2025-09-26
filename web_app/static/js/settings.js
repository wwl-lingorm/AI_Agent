// [file name]: web_app/static/js/settings.js
// [file content begin]
function initSettingsPage() {
    loadSystemInfo();
    loadSettings();
    setupEventListeners();
}

function setupEventListeners() {
    // Temperature滑块实时更新
    const temperatureSlider = document.getElementById('temperature');
    const temperatureValue = document.getElementById('temperatureValue');
    
    temperatureSlider.addEventListener('input', (e) => {
        temperatureValue.textContent = e.target.value;
    });
    
    // 各种设置变更监听
    document.getElementById('defaultModel').addEventListener('change', () => {
        showUnsavedChanges();
    });
    
    document.getElementById('maxTokens').addEventListener('change', () => {
        showUnsavedChanges();
    });
    
    // 其他设置项监听...
}

async function loadSystemInfo() {
    try {
        const response = await fetch('/api/system/status');
        const data = await response.json();
        
        const systemInfo = document.getElementById('systemInfo');
        systemInfo.innerHTML = `
            <div class="system-info-item">
                <div class="d-flex justify-content-between">
                    <strong>系统状态</strong>
                    <span class="badge ${data.status === 'running' ? 'bg-success' : 'bg-danger'}">
                        ${data.status === 'running' ? '运行中' : '异常'}
                    </span>
                </div>
            </div>
            <div class="system-info-item">
                <div class="d-flex justify-content-between">
                    <strong>可用模型数量</strong>
                    <span class="badge bg-info">${data.available_models.length}</span>
                </div>
            </div>
            <div class="system-info-item">
                <div class="d-flex justify-content-between">
                    <strong>活跃任务数</strong>
                    <span class="badge bg-warning">${data.active_tasks}</span>
                </div>
            </div>
            <div class="system-info-item">
                <div class="d-flex justify-content-between">
                    <strong>总任务数</strong>
                    <span class="badge bg-primary">${data.total_tasks}</span>
                </div>
            </div>
            <div class="system-info-item">
                <div class="d-flex justify-content-between">
                    <strong>Agent初始化状态</strong>
                    <span class="badge ${data.agents_initialized ? 'bg-success' : 'bg-danger'}">
                        ${data.agents_initialized ? '已初始化' : '未初始化'}
                    </span>
                </div>
            </div>
        `;
        
        // 更新可用模型下拉框
        updateModelOptions(data.available_models);
    } catch (error) {
        console.error('加载系统信息失败:', error);
        showError('加载系统信息失败: ' + error.message);
    }
}

function updateModelOptions(availableModels) {
    const select = document.getElementById('defaultModel');
    const options = select.querySelectorAll('option');
    
    options.forEach(option => {
        const isAvailable = availableModels.includes(option.value);
        option.disabled = !isAvailable;
        option.textContent = option.textContent.replace(' (不可用)', '') + (isAvailable ? '' : ' (不可用)');
    });
}

function loadSettings() {
    // 从localStorage加载保存的设置
    const settings = JSON.parse(localStorage.getItem('systemSettings') || '{}');
    
    // 应用设置到界面
    if (settings.defaultModel) {
        document.getElementById('defaultModel').value = settings.defaultModel;
    }
    if (settings.maxTokens) {
        document.getElementById('maxTokens').value = settings.maxTokens;
    }
    if (settings.temperature !== undefined) {
        document.getElementById('temperature').value = settings.temperature;
        document.getElementById('temperatureValue').textContent = settings.temperature;
    }
    if (settings.analysisTimeout) {
        document.getElementById('analysisTimeout').value = settings.analysisTimeout;
    }
    if (settings.maxConcurrentTasks) {
        document.getElementById('maxConcurrentTasks').value = settings.maxConcurrentTasks;
    }
    if (settings.logLevel) {
        document.getElementById('logLevel').value = settings.logLevel;
    }
    if (settings.logRetentionDays) {
        document.getElementById('logRetentionDays').value = settings.logRetentionDays;
    }
    if (settings.taskRetentionDays) {
        document.getElementById('taskRetentionDays').value = settings.taskRetentionDays;
    }
    
    // 复选框设置
    document.getElementById('enablePylint').checked = settings.enablePylint !== false;
    document.getElementById('enableMypy').checked = settings.enableMypy !== false;
    document.getElementById('enableBandit').checked = settings.enableBandit !== false;
    document.getElementById('autoSaveReports').checked = settings.autoSaveReports !== false;
    document.getElementById('enableWebsocket').checked = settings.enableWebsocket !== false;
    document.getElementById('enableNotifications').checked = settings.enableNotifications !== false;
}

function saveAllSettings() {
    const settings = {
        defaultModel: document.getElementById('defaultModel').value,
        maxTokens: parseInt(document.getElementById('maxTokens').value),
        temperature: parseFloat(document.getElementById('temperature').value),
        analysisTimeout: parseInt(document.getElementById('analysisTimeout').value),
        maxConcurrentTasks: parseInt(document.getElementById('maxConcurrentTasks').value),
        logLevel: document.getElementById('logLevel').value,
        logRetentionDays: parseInt(document.getElementById('logRetentionDays').value),
        taskRetentionDays: parseInt(document.getElementById('taskRetentionDays').value),
        enablePylint: document.getElementById('enablePylint').checked,
        enableMypy: document.getElementById('enableMypy').checked,
        enableBandit: document.getElementById('enableBandit').checked,
        autoSaveReports: document.getElementById('autoSaveReports').checked,
        enableWebsocket: document.getElementById('enableWebsocket').checked,
        enableNotifications: document.getElementById('enableNotifications').checked
    };
    
    // 保存到localStorage
    localStorage.setItem('systemSettings', JSON.stringify(settings));
    
    // 显示成功消息
    showSuccess('设置已保存！');
    hideUnsavedChanges();
    
    // 这里可以添加向后端发送设置的逻辑
    console.log('保存的设置:', settings);
}

function showUnsavedChanges() {
    // 可以添加未保存更改的提示
}

function hideUnsavedChanges() {
    // 隐藏未保存更改的提示
}

function downloadLogs() {
    // 模拟下载日志
    showInfo('日志下载功能暂未实现');
}

function exportData() {
    showInfo('数据导出功能暂未实现');
}

function clearOldTasks() {
    if (confirm('确定要清理过期任务吗？此操作不可恢复。')) {
        showInfo('清理过期任务功能暂未实现');
    }
}

function resetSystem() {
    if (confirm('确定要重置所有系统设置吗？此操作将恢复默认设置。')) {
        localStorage.removeItem('systemSettings');
        location.reload();
    }
}

function showSuccess(message) {
    showToast('success', message);
}

function showError(message) {
    showToast('error', message);
}

function showInfo(message) {
    showToast('info', message);
}

function showToast(type, message) {
    const alertClass = {
        'success': 'alert-success',
        'error': 'alert-danger',
        'info': 'alert-info',
        'warning': 'alert-warning'
    };
    
    const iconClass = {
        'success': 'fas fa-check-circle',
        'error': 'fas fa-exclamation-circle',
        'info': 'fas fa-info-circle',
        'warning': 'fas fa-exclamation-triangle'
    };
    
    const toast = document.createElement('div');
    toast.className = `alert ${alertClass[type]} alert-dismissible fade show position-fixed`;
    toast.style = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    toast.innerHTML = `
        <i class="${iconClass[type]} me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 3000);
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', initSettingsPage);
// [file content end]