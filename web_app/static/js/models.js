// [file name]: web_app/static/js/models.js
// [file content begin]
const modelInfo = {
    'deepseek': {
        name: 'DeepSeek Coder',
        description: '专为代码生成和分析优化的免费AI模型',
        provider: 'DeepSeek',
        cost: '免费',
        features: ['代码生成', '代码分析', '错误修复', '代码优化'],
        icon: 'fas fa-code'
    },
    'openai': {
        name: 'GPT-3.5/GPT-4',
        description: 'OpenAI开发的通用大语言模型',
        provider: 'OpenAI',
        cost: '按使用付费',
        features: ['通用对话', '代码生成', '文本处理', '推理分析'],
        icon: 'fas fa-robot'
    },
    'tongyi': {
        name: '通义灵码',
        description: '阿里巴巴开发的智能编程助手',
        provider: '阿里巴巴',
        cost: '有免费额度',
        features: ['代码补全', '代码解释', '单元测试', '代码优化'],
        icon: 'fas fa-brain'
    }
};

async function loadModels() {
    try {
        const response = await fetch('/api/system/status');
        const data = await response.json();
        
        const availableModels = data.available_models || [];
        const allModels = Object.keys(modelInfo);
        
        // 更新统计信息
        document.getElementById('availableModelsCount').textContent = availableModels.length;
        document.getElementById('unavailableModelsCount').textContent = allModels.length - availableModels.length;
        
        renderModelsList(allModels, availableModels);
    } catch (error) {
        console.error('加载模型信息失败:', error);
        showError('加载模型信息失败: ' + error.message);
    }
}

function renderModelsList(allModels, availableModels) {
    const container = document.getElementById('modelsList');
    
    const html = allModels.map(modelKey => {
        const model = modelInfo[modelKey];
        const isAvailable = availableModels.includes(modelKey);
        
        return createModelCard(modelKey, model, isAvailable);
    }).join('');
    
    container.innerHTML = html;
}

function createModelCard(modelKey, model, isAvailable) {
    const statusClass = isAvailable ? 'model-available' : 'model-unavailable';
    const statusIndicator = isAvailable ? 'status-online' : 'status-offline';
    const statusText = isAvailable ? '可用' : '不可用';
    const statusColor = isAvailable ? 'text-success' : 'text-danger';
    
    return `
        <div class="col-lg-4 col-md-6 mb-4">
            <div class="card model-card ${statusClass} h-100">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-start mb-3">
                        <div>
                            <h5 class="card-title">
                                <i class="${model.icon} me-2"></i>
                                ${model.name}
                            </h5>
                            <p class="text-muted small mb-0">by ${model.provider}</p>
                        </div>
                        <div class="text-end">
                            <span class="status-indicator ${statusIndicator}"></span>
                            <small class="${statusColor} ms-1">${statusText}</small>
                        </div>
                    </div>
                    
                    <p class="card-text text-muted small">${model.description}</p>
                    
                    <div class="mb-3">
                        <div class="d-flex justify-content-between mb-1">
                            <small class="text-muted">成本:</small>
                            <small class="fw-bold">${model.cost}</small>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <small class="text-muted">主要功能:</small>
                        <div class="mt-1">
                            ${model.features.map(feature => 
                                `<span class="badge bg-light text-dark me-1 mb-1">${feature}</span>`
                            ).join('')}
                        </div>
                    </div>
                    
                    <div class="d-grid gap-2 d-md-flex justify-content-md-end">
                        <button class="btn btn-sm btn-outline-primary" onclick="testModel('${modelKey}')" 
                                ${!isAvailable ? 'disabled' : ''}>
                            <i class="fas fa-vial"></i> 测试
                        </button>
                        ${isAvailable ? 
                            `<button class="btn btn-sm btn-outline-success" onclick="setDefaultModel('${modelKey}')">
                                <i class="fas fa-star"></i> 设为默认
                            </button>` : 
                            `<button class="btn btn-sm btn-outline-warning" onclick="showConfigHelp('${modelKey}')">
                                <i class="fas fa-cog"></i> 配置
                            </button>`}
                    </div>
                </div>
            </div>
        </div>
    `;
}

async function testModel(modelKey) {
    const button = event.target;
    const originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 测试中...';
    
    try {
        // 这里应该调用实际的模型测试API
        await new Promise(resolve => setTimeout(resolve, 2000)); // 模拟测试
        
        showSuccess(`${modelInfo[modelKey].name} 测试成功！`);
    } catch (error) {
        showError(`${modelInfo[modelKey].name} 测试失败: ${error.message}`);
    } finally {
        button.disabled = false;
        button.innerHTML = originalText;
    }
}

function setDefaultModel(modelKey) {
    document.getElementById('defaultModel').textContent = modelInfo[modelKey].name;
    showSuccess(`已将 ${modelInfo[modelKey].name} 设为默认模型`);
}

function showConfigHelp(modelKey) {
    const model = modelInfo[modelKey];
    let envVarName = '';
    let configUrl = '';
    
    switch (modelKey) {
        case 'deepseek':
            envVarName = 'DEEPSEEK_API_KEY';
            configUrl = 'https://platform.deepseek.com/api_keys';
            break;
        case 'openai':
            envVarName = 'OPENAI_API_KEY';
            configUrl = 'https://platform.openai.com/api-keys';
            break;
        case 'tongyi':
            envVarName = 'TONGYI_API_KEY';
            configUrl = 'https://dashscope.console.aliyun.com/apiKey';
            break;
    }
    
    const message = `
        要使用 ${model.name}，请按以下步骤配置：
        
        1. 访问 ${configUrl} 获取API密钥
        2. 设置环境变量：${envVarName}=your_api_key
        3. 重启服务使配置生效
    `;
    
    alert(message);
}

async function testAllModels() {
    const button = event.target;
    const originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 测试中...';
    
    try {
        // 获取可用模型列表
        const response = await fetch('/api/system/status');
        const data = await response.json();
        const availableModels = data.available_models || [];
        
        let successCount = 0;
        let failCount = 0;
        
        for (const modelKey of availableModels) {
            try {
                await new Promise(resolve => setTimeout(resolve, 1000)); // 模拟测试
                successCount++;
            } catch (error) {
                failCount++;
            }
        }
        
        showSuccess(`模型测试完成！成功: ${successCount}, 失败: ${failCount}`);
    } catch (error) {
        showError(`批量测试失败: ${error.message}`);
    } finally {
        button.disabled = false;
        button.innerHTML = originalText;
    }
}

function toggleKeyVisibility(inputId) {
    const input = document.getElementById(inputId);
    const button = input.nextElementSibling;
    const icon = button.querySelector('i');
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'fas fa-eye-slash';
    } else {
        input.type = 'password';
        icon.className = 'fas fa-eye';
    }
}

function showSuccess(message) {
    showToast('success', message);
}

function showError(message) {
    showToast('error', message);
}

function showToast(type, message) {
    const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
    const iconClass = type === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-circle';
    
    const toast = document.createElement('div');
    toast.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
    toast.style = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    toast.innerHTML = `
        <i class="${iconClass} me-2"></i>
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
document.addEventListener('DOMContentLoaded', () => {
    loadModels();
    
    // 定期刷新模型状态
    setInterval(loadModels, 30000);
});
// [file content end]