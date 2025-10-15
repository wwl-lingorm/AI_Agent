## 1. 静态错误（按工具分类）

> 注：DetectionAgent 会先通过 AST 收集仓库顶层 import 名，已改进为在单文件场景将该文件的目录视为 repo root，从而避免把同仓库文件误判为缺失依赖。对不存在的第三方模块可临时生成 stub（仅用于静态分析）。

### 1.1 Pylint（代码质量与常见错误）

- 可检测问题
  - Import 失败（`Unable to import 'X'`）  
  - 命名规范、未使用变量、未使用导入  
  - 明确的语法或格式问题（少量）  
  - 可能的运行时风险提示（例如格式化/参数问题）
- 修复策略
  - 如果为本地模块：调整 PYTHONPATH / 相对导入（已在 DetectionAgent 中处理）  
  - 第三方缺失：建议安装依赖或生成临时 stub（用于静态分析）  
  - 命名/未使用变量：LLM 自动删减或重命名（低风险）  
  - 语法类：LLM 自动修复（高成功率，对小改动可自动应用）

### 1.2 MyPy（类型检查）
- 可检测问题
  - 类型不匹配、属性不存在、函数签名错误
- 修复策略
  - 添加/调整类型注解、插入类型转换或 defensive checks  
  - 对外部包缺失类型：建议安装 types- 包或生成 `.pyi` stub

### 1.3 Flake8（风格）
- 可检测问题
  - 行长度、空白、未使用导入等风格问题
- 修复策略
  - 自动格式化（black/ruff/isort）或 LLM 修改风格相关行

### 1.4 Bandit（安全扫描）
- 可检测问题
  - 不安全 API（`eval`, `pickle.loads` 等）、不安全的临时文件处理
- 修复策略
  - 建议替换为更安全的 API、加入输入校验、或限定权限

### 1.5 Safety（依赖漏洞）
- 可检测问题
  - requirements/依赖中公开的已知安全漏洞
- 修复策略
  - 建议升级或替换依赖版本；提供 pip 升级命令（供人工执行或 CI 自动化）

### 1.6 JS/TS（eslint, tsc）
- 可检测问题
  - 语法错误、类型错误、风格问题
- 修复策略
  - LLM 或自动化修复语法/简单类型错误；复杂类型错误建议人工处理或增补类型声明

### 1.7 Import 检查与 stub 生成
- 功能说明
  - 通过 AST 收集顶层 import，过滤项目内模块（现支持单文件同目录识别），对缺失的第三方包生成临时 stub（只用于静态分析）
- 风险
  - stub 不能代表真实实现，可能掩盖逻辑错误；仅用于让分析工具继续工作

---

## 2. 动态错误（运行时问题）
DetectionAgent 主要做静态检测；RepairAgent + ValidationAgent 可触发运行或构造运行场景来捕捉动态错误，常见类型：

- 导入时异常（ImportError）——典型原因：模块未安装或路径错误
- 资源缺失（FileNotFoundError / OSError）——缺少图像、声音、数据文件
- API 使用错误（TypeError、ValueError）——参数不匹配或不当类型
- 子进程/系统调用失败（WinError、ENOENT）——依赖外部可执行或文件缺失
- 并发/死锁/超时——需集成测试复现，难以纯静态捕获

修复策略示例：
- 资源缺失：修正路径（使用 `os.path.join(base_dir, ...)`）、提供 fallback 占位资源、或在启动时验证资源完整性并提示
- 依赖未安装：建议添加 `requirements.txt` 或给出 `pip install` 命令
- 调用错误：修正调用签名、插入类型/值转换或增加参数校验
- 并发问题：建议加锁或任务重试逻辑（人工验证为佳）

---

## 3. RepairAgent（LLM）能做的修复与风险分级

### 3.1 输出结构（典型）
每个 repair result 包含（示例字段）
- `result_type`: `"static"` 或 `"dynamic"`
- `code_before`: 原始代码片段
- `code_after`: 修复后代码（可直接写入 `repair_outputs`）
- `diff_html`: 可在 UI 显示的差异
- `fix_suggestion`: 文本说明与理由
- `metadata`: model name、confidence 等（可选）

### 3.2 修复模式与自动化级别
- 低风险、可自动应用（Fully automated）
  - 格式化、拼写、简单语法修正、删除未使用导入
- 中风险、半自动（建议人工审查）
  - API 参数修正、相对/绝对 import 调整、引入小规模 defensive checks
- 高风险、仅建议（人工必须审核）
  - 大范围重构、算法改写、改变功能行为

### 3.3 动态修复
- 增加 try/except、检查资源存在、添加 fallback
- 这些改变可能掩盖根本缺陷，需通过自动化/手动测试验证

