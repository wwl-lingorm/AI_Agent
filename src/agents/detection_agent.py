import subprocess
import json
import os
import ast
import tempfile
import shutil
import importlib.util
from .base_agent import BaseAgent
from typing import Dict, Any, List

class DetectionAgent(BaseAgent):
    def __init__(self):
        super().__init__("DetectionAgent", "负责检测代码缺陷")
        self.tool_config = {
            'python': ['pylint', 'mypy', 'bandit'],  # 安全扫描
            'javascript': ['eslint'],
            'typescript': ['eslint', 'tsc'],  # TypeScript编译器
            'java': ['checkstyle', 'pmd'],
            'cpp': ['cppcheck']
        }
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        self.log("开始缺陷检测")
        repo_path = task.get("repo_path")
        if not repo_path:
            return {"status": "error", "error": "代码库路径无效"}
        # 支持单文件检测
        if os.path.isfile(repo_path) and repo_path.endswith('.py'):
            project_language = 'python'
        else:
            project_language = self._detect_project_language(repo_path)
        self.log(f"检测到项目语言: {project_language}")
        # 为了让静态检查工具解析项目内部导入，尝试创建针对缺失第三方模块的临时 stub 包
        temp_stub_dir = None
        try:
            import_names = self._collect_top_level_imports(repo_path)
            missing = []
            # Ensure local project dir is visible to importlib during spec checks
            import sys
            repo_abs = os.path.abspath(repo_path)
            repo_root_dir = os.path.dirname(repo_abs) if os.path.isfile(repo_abs) else repo_abs
            added_to_syspath = False
            try:
                if repo_root_dir and repo_root_dir not in sys.path:
                    sys.path.insert(0, repo_root_dir)
                    added_to_syspath = True

                for name in sorted(import_names):
                    # skip stdlib detection by checking spec
                    try:
                        spec = importlib.util.find_spec(name)
                        if spec is None:
                            missing.append(name)
                    except Exception:
                        missing.append(name)
            finally:
                if added_to_syspath:
                    try:
                        sys.path.remove(repo_root_dir)
                    except Exception:
                        pass

            if missing:
                self.log(f"生成临时 stub 模块以帮助静态分析: {missing}")
                temp_stub_dir = self._create_stub_modules(missing)

            # 运行对应的分析工具（并行执行以加速）
            analysis_results = {}
            all_issues = []
            available_tools = self.tool_config.get(project_language, [])

            # 扩展支持 flake8, safety（如果python）
            if project_language == 'python':
                if 'flake8' not in available_tools:
                    available_tools.append('flake8')
                if 'safety' not in available_tools:
                    available_tools.append('safety')

            # 并行执行工具
            import asyncio
            tasks = []
            for tool in available_tools:
                if self._is_tool_available(tool):
                    target_path = repo_path if os.path.isfile(repo_path) and repo_path.endswith('.py') else repo_path
                    tasks.append(self._run_analysis_tool(tool, target_path, project_language))
                else:
                    self.log(f"工具 {tool} 不可用", "warning")
                    analysis_results[tool] = {"available": False, "error": "工具未安装", "issues": []}

            if tasks:
                results = await asyncio.gather(*tasks)
                # 合并结果，注意对应顺序：filter later
                res_tools = [t for t in available_tools if t not in analysis_results]
                for tool_name, result in zip(res_tools, results):
                    analysis_results[tool_name] = result
                    if result.get("available", True) and "issues" in result:
                        all_issues.extend(result["issues"])
            
            # 汇总结构化输出
            summary = {
                "total_issues": len(all_issues),
                "by_tool": {tool: len(analysis_results.get(tool, {}).get("issues", [])) for tool in list(analysis_results.keys())}
            }
            return {
                "status": "completed",
                "defects_found": len(all_issues),
                "language": project_language,
                "tools_used": list(analysis_results.keys()),
                "analysis_results": analysis_results,
                "all_issues": all_issues,
                "summary": summary
            }
        except Exception as e:
            self.log(f"检测执行失败: {e}", "error")
            return {"status": "error", "error": str(e)}
        finally:
            # 清理临时 stub
            try:
                if temp_stub_dir and os.path.exists(temp_stub_dir):
                    shutil.rmtree(temp_stub_dir)
                    self.log(f"清理临时 stub 目录: {temp_stub_dir}")
            except Exception:
                pass

    def _collect_top_level_imports(self, repo_path: str) -> set:
        """扫描项目中所有 Python 文件，收集顶层 import 名称（不带子模块）。"""
        names = set()
        if os.path.isfile(repo_path) and repo_path.endswith('.py'):
            files = [repo_path]
        else:
            files = []
            for root, dirs, fnames in os.walk(repo_path):
                # skip virtualenvs and binary dirs
                dirs[:] = [d for d in dirs if d not in ('.venv', 'venv', '__pycache__', '.git')]
                for f in fnames:
                    if f.endswith('.py'):
                        files.append(os.path.join(root, f))
        for fp in files:
            try:
                with open(fp, 'r', encoding='utf-8') as fh:
                    src = fh.read()
                tree = ast.parse(src)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for n in node.names:
                            top = n.name.split('.')[0]
                            names.add(top)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            top = node.module.split('.')[0]
                            names.add(top)
            except Exception:
                continue
        # filter obvious project-local names by removing modules that exist under repo_path
        filtered = set()
        # If repo_path is a single file, also treat its directory as project root
        repo_base = repo_path
        if os.path.isfile(repo_path):
            repo_base = os.path.dirname(repo_path)

        for n in names:
            # if repo contains a module with that name, skip
            candidate_file = os.path.join(repo_base, f"{n}.py")
            candidate_pkg = os.path.join(repo_base, n)
            if os.path.exists(candidate_file) or os.path.isdir(candidate_pkg):
                continue
            filtered.add(n)
        return filtered

    def _create_stub_modules(self, names: List[str]) -> str:
        """在临时目录生成最小 stub 模块/包，返回临时目录路径。"""
        tmpdir = tempfile.mkdtemp(prefix='py_stub_')
        for name in names:
            # if name looks like a package (contains no hyphen etc.), create package dir
            if not name.isidentifier():
                # skip invalid identifiers
                continue
            pkg_dir = os.path.join(tmpdir, name)
            try:
                os.makedirs(pkg_dir, exist_ok=True)
                with open(os.path.join(pkg_dir, '__init__.py'), 'w', encoding='utf-8') as f:
                    f.write('# auto-generated stub package for analysis\n')
                    f.write('from typing import Any\n')
                    f.write('Any = Any\n')
            except Exception:
                # fallback to single module file
                try:
                    with open(os.path.join(tmpdir, f'{name}.py'), 'w', encoding='utf-8') as f:
                        f.write('# auto-generated stub module for analysis\n')
                        f.write('from typing import Any\n')
                        f.write('Any = Any\n')
                except Exception:
                    continue
        return tmpdir
    
    def _detect_project_language(self, repo_path: str) -> str:
        """检测项目主要编程语言"""
        extension_count = {}
        
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                if '.' in file:
                    ext = file.split('.')[-1].lower()
                    extension_count[ext] = extension_count.get(ext, 0) + 1
        
        # 根据文件扩展名判断语言
        lang_map = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'cpp',
            'h': 'cpp'
        }
        
        for ext, count in sorted(extension_count.items(), key=lambda x: x[1], reverse=True):
            if ext in lang_map:
                return lang_map[ext]
        
        return 'python'  # 默认

    def _prepare_subprocess_env_and_cwd(self, repo_path: str):
        """Prepare environment and cwd for subprocess calls so tools can resolve local imports.

        Returns (env, cwd)
        """
        env = os.environ.copy()
        repo_abs = os.path.abspath(repo_path)
        if os.path.isfile(repo_abs):
            repo_dir = os.path.dirname(repo_abs)
        else:
            repo_dir = repo_abs

        # Prepend repo_dir to PYTHONPATH so python -m tools can import project modules
        if repo_dir:
            existing = env.get('PYTHONPATH', '')
            if existing:
                env['PYTHONPATH'] = repo_dir + os.pathsep + existing
            else:
                env['PYTHONPATH'] = repo_dir

        # Use repo_dir as cwd for tools when analyzing a project; for single-file, use containing dir
        cwd = repo_dir if repo_dir and os.path.isdir(repo_dir) else repo_dir
        return env, cwd
    
    def _is_tool_available(self, tool: str) -> bool:
        """检查工具是否可用"""
        try:
            # 使用 python -m 方式运行工具，确保使用正确的环境
            import sys
            python_executable = sys.executable
            self.log(f"检查工具 {tool} 是否可用，使用Python: {python_executable}")
            
            result = subprocess.run([python_executable, '-m', tool, '--version'], 
                         capture_output=True, check=True, timeout=10)
            self.log(f"工具 {tool} 可用: {result.stdout.decode().strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            self.log(f"使用 -m 方式检查工具 {tool} 失败: {str(e)}")
            # 如果 -m 方式失败，尝试直接调用
            try:
                result = subprocess.run([tool, '--version'], capture_output=True, check=True, timeout=10)
                self.log(f"工具 {tool} 直接调用可用: {result.stdout.decode().strip()}")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e2:
                self.log(f"直接调用工具 {tool} 也失败: {str(e2)}")
                return False
    
    async def _run_analysis_tool(self, tool: str, repo_path: str, language: str) -> Dict[str, Any]:
        """运行指定的分析工具"""
        try:
            if tool == 'pylint':
                return await self._run_pylint(repo_path)
            elif tool == 'mypy':
                return await self._run_mypy(repo_path)
            elif tool == 'eslint':
                return await self._run_eslint(repo_path)
            elif tool == 'bandit':
                return await self._run_bandit(repo_path)
            elif tool == 'tsc':
                return await self._run_typescript_compiler(repo_path)
            else:
                return {"available": True, "issues": [], "error": f"未知工具: {tool}"}
        except Exception as e:
            return {"available": True, "issues": [], "error": f"工具执行错误: {str(e)}"}
    
    async def _run_pylint(self, repo_path: str) -> Dict[str, Any]:
        """运行Pylint，输出标准化问题结构"""
        try:
            import sys
            python_executable = sys.executable
            env, cwd = self._prepare_subprocess_env_and_cwd(repo_path)
            result = subprocess.run([
                python_executable, '-m', 'pylint', '--output-format=json', repo_path
            ], capture_output=True, text=True, timeout=60, env=env, cwd=cwd)
            issues = []
            # pylint返回码说明:
            # 0: 无问题
            # 1: fatal message issued (致命错误)
            # 2: error message issued (错误)
            # 4: warning message issued (警告)  
            # 8: refactor message issued (重构建议)
            # 16: convention message issued (约定)
            # 32: usage error (使用错误)
            # 可以组合，比如 1+2+4 = 7 表示有fatal、error、warning
            if result.returncode < 32 or result.returncode == 32:  # 接受所有正常的pylint返回码
                try:
                    raw = json.loads(result.stdout) if result.stdout else []
                    for item in raw:
                        issues.append({
                            "file": item.get("path"),
                            "line": item.get("line"),
                            "type": item.get("type"),
                            "symbol": item.get("symbol"),
                            "message": item.get("message"),
                            "tool": "pylint"
                        })
                except json.JSONDecodeError as e:
                    return {"available": True, "issues": [], "error": f"JSON解析失败: {str(e)}"}
                
                return {
                    "available": True,
                    "issues": issues,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                }
            else:
                return {"available": True, "issues": [], "error": f"Pylint执行失败 (返回码: {result.returncode}): {result.stderr}"}
        except subprocess.TimeoutExpired:
            return {"available": True, "issues": [], "error": "执行超时"}
    
    async def _run_mypy(self, repo_path: str) -> Dict[str, Any]:
        """运行MyPy类型检查，输出标准化问题结构"""
        try:
            import sys
            python_executable = sys.executable
            env, cwd = self._prepare_subprocess_env_and_cwd(repo_path)
            result = subprocess.run([
                python_executable, '-m', 'mypy', repo_path, '--ignore-missing-imports', '--no-error-summary'
            ], capture_output=True, text=True, timeout=60, env=env, cwd=cwd)
            issues = []
            if result.returncode != 0:
                for line in result.stdout.split('\n'):
                    if line.strip() and 'error:' in line:
                        # 解析格式: file:line: error: ...
                        parts = line.split(':', 3)
                        if len(parts) >= 4:
                            issues.append({
                                "file": parts[0].strip(),
                                "line": int(parts[1]),
                                "type": "type_error",
                                "message": parts[3].strip(),
                                "tool": "mypy"
                            })
                        else:
                            issues.append({
                                "file": None,
                                "line": None,
                                "type": "type_error",
                                "message": line.strip(),
                                "tool": "mypy"
                            })
            return {
                "available": True,
                "issues": issues,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired:
            return {"available": True, "issues": [], "error": "执行超时"}

    async def _run_flake8(self, repo_path: str) -> Dict[str, Any]:
        try:
            import sys
            python_executable = sys.executable
            # 使用 --format=json 需要 flake8-json插件，不一定可用，回退为文本解析
            env, cwd = self._prepare_subprocess_env_and_cwd(repo_path)
            result = subprocess.run([python_executable, '-m', 'flake8', '--format=json', repo_path], capture_output=True, text=True, timeout=60, env=env, cwd=cwd)
            issues = []
            try:
                if result.stdout:
                    j = json.loads(result.stdout)
                    # expected format: {"path": [{"line_number":..., "text":...}, ...]}
                    for path, items in j.items():
                        for it in items:
                            issues.append({
                                "file": path,
                                "line": it.get('line_number'),
                                "message": it.get('text'),
                                "tool": 'flake8'
                            })
                else:
                    # 回退文本解析
                    for line in result.stderr.split('\n') + result.stdout.split('\n'):
                        if line.strip():
                            parts = line.split(':', 3)
                            if len(parts) >= 4:
                                issues.append({
                                    'file': parts[0].strip(),
                                    'line': int(parts[1]),
                                    'message': parts[3].strip(),
                                    'tool': 'flake8'
                                })
            except Exception:
                pass
            return {"available": True, "issues": issues, "stdout": result.stdout, "stderr": result.stderr}
        except subprocess.TimeoutExpired:
            return {"available": True, "issues": [], "error": "flake8 执行超时"}
        except FileNotFoundError:
            return {"available": False, "issues": [], "error": "flake8 未安装"}

    async def _run_safety(self, repo_path: str) -> Dict[str, Any]:
        try:
            # safety 通常检查 requirements.txt 或 pip freeze 输出
            import sys, tempfile
            python_executable = sys.executable
            # 尝试读取 requirements.txt
            reqs = None
            req_path = os.path.join(repo_path, 'requirements.txt') if os.path.isdir(repo_path) else None
            if req_path and os.path.exists(req_path):
                reqs = open(req_path).read()
            else:
                # 生成依赖列表
                env, cwd = self._prepare_subprocess_env_and_cwd(repo_path)
                proc = subprocess.run([python_executable, '-m', 'pip', 'freeze'], capture_output=True, text=True, timeout=30, env=env, cwd=cwd)
                reqs = proc.stdout
            with tempfile.NamedTemporaryFile('w', delete=False) as f:
                f.write(reqs)
                tmp = f.name
            env, cwd = self._prepare_subprocess_env_and_cwd(repo_path)
            result = subprocess.run([python_executable, '-m', 'safety', 'check', '--file', tmp, '--json'], capture_output=True, text=True, timeout=60, env=env, cwd=cwd)
            issues = []
            try:
                if result.stdout:
                    j = json.loads(result.stdout)
                    for it in j:
                        issues.append({
                            'file': None,
                            'line': None,
                            'type': 'vulnerability',
                            'message': it.get('advisory'),
                            'tool': 'safety'
                        })
            except Exception:
                pass
            return {"available": True, "issues": issues, "stdout": result.stdout, "stderr": result.stderr}
        except subprocess.TimeoutExpired:
            return {"available": True, "issues": [], "error": "safety 执行超时"}
        except FileNotFoundError:
            return {"available": False, "issues": [], "error": "safety 未安装"}
    
    async def _run_eslint(self, repo_path: str) -> Dict[str, Any]:
        """运行ESLint"""
        try:
            # 检查是否有ESLint配置
            eslint_configs = ['.eslintrc.js', '.eslintrc.json', '.eslintrc.yml', '.eslintrc']
            has_config = any(os.path.exists(os.path.join(repo_path, config)) for config in eslint_configs)
            
            if not has_config:
                return {"available": True, "issues": [], "warning": "未找到ESLint配置"}
            
            # ESLint runs with cwd set to project root
            env, cwd = self._prepare_subprocess_env_and_cwd(repo_path)
            result = subprocess.run([
                'npx', 'eslint', '.', '--format=json'
            ], capture_output=True, text=True, cwd=cwd or repo_path, timeout=60, env=env)
            
            if result.returncode in [0, 1]:  # 0: 无错误, 1: 有错误
                try:
                    output = result.stdout.strip()
                    if output:
                        issues = json.loads(output)
                        # 扁平化ESLint输出
                        flat_issues = []
                        for file_issues in issues:
                            for issue in file_issues.get("messages", []):
                                flat_issues.append({
                                    "file": file_issues.get("filePath"),
                                    "line": issue.get("line"),
                                    "message": issue.get("message"),
                                    "rule": issue.get("ruleId"),
                                    "severity": issue.get("severity"),
                                    "tool": "eslint"
                                })
                        return {
                            "available": True,
                            "issues": flat_issues,
                            "stdout": result.stdout,
                            "stderr": result.stderr
                        }
                    else:
                        return {"available": True, "issues": []}
                except json.JSONDecodeError:
                    return {"available": True, "issues": [], "error": "JSON解析失败"}
            else:
                return {"available": True, "issues": [], "error": result.stderr}
        except subprocess.TimeoutExpired:
            return {"available": True, "issues": [], "error": "执行超时"}
        except FileNotFoundError:
            return {"available": False, "issues": [], "error": "ESLint未安装"}
    
    async def _run_bandit(self, repo_path: str) -> Dict[str, Any]:
        """运行Bandit安全扫描，输出标准化问题结构"""
        try:
            import sys
            python_executable = sys.executable
            # 如果是单文件，直接扫描文件；如果是目录，递归扫描
            if os.path.isfile(repo_path):
                env, cwd = self._prepare_subprocess_env_and_cwd(repo_path)
                result = subprocess.run([
                    python_executable, '-m', 'bandit', '-f', 'json', repo_path
                ], capture_output=True, text=True, timeout=60, env=env, cwd=cwd)
            else:
                env, cwd = self._prepare_subprocess_env_and_cwd(repo_path)
                result = subprocess.run([
                    python_executable, '-m', 'bandit', '-r', '-f', 'json', repo_path
                ], capture_output=True, text=True, timeout=60, env=env, cwd=cwd)
            issues = []
            if result.returncode in [0, 1]:
                try:
                    bandit_json = json.loads(result.stdout) if result.stdout else {}
                    for item in bandit_json.get("results", []):
                        issues.append({
                            "file": item.get("filename"),
                            "line": item.get("line_number"),
                            "type": item.get("test_id"),
                            "message": item.get("issue_text"),
                            "severity": item.get("issue_severity"),
                            "confidence": item.get("issue_confidence"),
                            "tool": "bandit"
                        })
                    return {
                        "available": True,
                        "issues": issues,
                        "stdout": result.stdout,
                        "stderr": result.stderr
                    }
                except json.JSONDecodeError:
                    return {"available": True, "issues": [], "error": "JSON解析失败"}
            else:
                return {"available": True, "issues": [], "error": result.stderr}
        except subprocess.TimeoutExpired:
            return {"available": True, "issues": [], "error": "执行超时"}
    
    async def _run_typescript_compiler(self, repo_path: str) -> Dict[str, Any]:
        """运行TypeScript编译器检查"""
        try:
            # 检查是否有tsconfig.json
            tsconfig_path = os.path.join(repo_path, 'tsconfig.json')
            if not os.path.exists(tsconfig_path):
                return {"available": True, "issues": [], "warning": "未找到tsconfig.json"}
            
            result = subprocess.run([
                'npx', 'tsc', '--noEmit', '--pretty', 'false'
            ], capture_output=True, text=True, cwd=repo_path, timeout=60)
            
            issues = []
            if result.returncode != 0:
                for line in result.stderr.split('\n'):
                    if line.strip() and ('error' in line.lower() or 'warning' in line.lower()):
                        issues.append({
                            "type": "compilation_error",
                            "message": line.strip(),
                            "tool": "tsc"
                        })
            
            return {
                "available": True,
                "issues": issues,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.TimeoutExpired:
            return {"available": True, "issues": [], "error": "执行超时"}