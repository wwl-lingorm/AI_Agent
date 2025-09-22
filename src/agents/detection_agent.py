import subprocess
import json
import os
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
        
        # 检测项目语言
        project_language = self._detect_project_language(repo_path)
        self.log(f"检测到项目语言: {project_language}")
        
        # 运行对应的分析工具
        analysis_results = {}
        available_tools = self.tool_config.get(project_language, [])
        
        for tool in available_tools:
            if self._is_tool_available(tool):
                result = await self._run_analysis_tool(tool, repo_path, project_language)
                analysis_results[tool] = result
            else:
                self.log(f"工具 {tool} 不可用", "warning")
                analysis_results[tool] = {"available": False, "error": "工具未安装"}
        
        # 汇总结果
        all_issues = []
        for tool, result in analysis_results.items():
            if result.get("available", True) and "issues" in result:
                all_issues.extend(result["issues"])
        
        return {
            "status": "completed",
            "defects_found": len(all_issues),
            "language": project_language,
            "tools_used": list(analysis_results.keys()),
            "analysis_results": analysis_results,
            "all_issues": all_issues,
            "summary": f"使用 {len(analysis_results)} 个工具发现 {len(all_issues)} 个问题"
        }
    
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
    
    def _is_tool_available(self, tool: str) -> bool:
        """检查工具是否可用"""
        try:
            subprocess.run([tool, '--version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
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
        """运行Pylint"""
        try:
            result = subprocess.run([
                'pylint', '--output-format=json', repo_path
            ], capture_output=True, text=True, cwd=repo_path, timeout=60)
            
            if result.returncode in [0, 4, 8, 16, 32]:  # Pylint的各种退出码
                issues = json.loads(result.stdout) if result.stdout else []
                return {
                    "available": True,
                    "issues": issues,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
            else:
                return {"available": True, "issues": [], "error": result.stderr}
        except subprocess.TimeoutExpired:
            return {"available": True, "issues": [], "error": "执行超时"}
    
    async def _run_mypy(self, repo_path: str) -> Dict[str, Any]:
        """运行MyPy类型检查"""
        try:
            result = subprocess.run([
                'mypy', repo_path, '--ignore-missing-imports', '--no-error-summary'
            ], capture_output=True, text=True, cwd=repo_path, timeout=60)
            
            issues = []
            if result.returncode != 0:
                for line in result.stdout.split('\n'):
                    if line.strip() and 'error:' in line:
                        issues.append({
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
    
    async def _run_eslint(self, repo_path: str) -> Dict[str, Any]:
        """运行ESLint"""
        try:
            # 检查是否有ESLint配置
            eslint_configs = ['.eslintrc.js', '.eslintrc.json', '.eslintrc.yml', '.eslintrc']
            has_config = any(os.path.exists(os.path.join(repo_path, config)) for config in eslint_configs)
            
            if not has_config:
                return {"available": True, "issues": [], "warning": "未找到ESLint配置"}
            
            result = subprocess.run([
                'npx', 'eslint', '.', '--format=json'
            ], capture_output=True, text=True, cwd=repo_path, timeout=60)
            
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
        """运行Bandit安全扫描"""
        try:
            result = subprocess.run([
                'bandit', '-r', '-f', 'json', repo_path
            ], capture_output=True, text=True, cwd=repo_path, timeout=60)
            
            if result.returncode in [0, 1]:  # Bandit的退出码
                try:
                    issues = json.loads(result.stdout) if result.stdout else []
                    return {
                        "available": True,
                        "issues": issues.get("results", []),
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