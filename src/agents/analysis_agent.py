import ast
import os
from .base_agent import BaseAgent
from typing import Dict, Any

class AnalysisAgent(BaseAgent):
    def __init__(self):
        super().__init__("AnalysisAgent", "负责分析代码结构和理解项目上下文")
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        self.log(f"开始代码分析: {task.get('repo_path')}")
        repo_path = task.get("repo_path")
        if not repo_path or not os.path.exists(repo_path):
            return {"status": "error", "error": "代码库路径或文件无效"}
        # 支持单文件分析
        if os.path.isfile(repo_path):
            analysis_result = self._analyze_single_file(repo_path)
        else:
            analysis_result = self._analyze_code_structure(repo_path)
        return {
            "status": "completed",
            "files_analyzed": len(analysis_result.get("files", [])),
            "structure": analysis_result,
            "summary": "代码结构分析完成"
        }

    def _analyze_single_file(self, file_path: str) -> Dict[str, Any]:
        """分析单个Python文件，结构与多文件一致"""
        result = {"files": []}
        if file_path.endswith('.py'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                tree = ast.parse(content)
                file_info = self._analyze_python_file(tree, file_path, content)
                result["files"].append(file_info)
            except Exception as e:
                self.log(f"分析文件 {file_path} 时出错: {str(e)}", "error")
        return result
    
    def _analyze_code_structure(self, repo_path: str) -> Dict[str, Any]:
        """分析代码结构，支持目录和单文件，输出详细结构信息"""
        result = {"files": []}
        if os.path.isfile(repo_path) and repo_path.endswith('.py'):
            # 单文件分析
            try:
                with open(repo_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                tree = ast.parse(content)
                file_info = self._analyze_python_file(tree, repo_path, content)
                result["files"].append(file_info)
            except Exception as e:
                self.log(f"分析文件 {repo_path} 时出错: {str(e)}", "error")
        else:
            # 目录分析
            for root, dirs, files in os.walk(repo_path):
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            tree = ast.parse(content)
                            file_info = self._analyze_python_file(tree, file_path, content)
                            result["files"].append(file_info)
                        except Exception as e:
                            self.log(f"分析文件 {file_path} 时出错: {str(e)}", "error")
        return result
    
    def _analyze_python_file(self, tree, file_path: str, content: str) -> Dict[str, Any]:
        """分析单个Python文件，输出函数、类、导入、全局变量、注释、文档字符串等，并包含原始内容"""
        file_info = {
            "path": file_path,
            "functions": [],
            "classes": [],
            "imports": [],
            "globals": [],
            "docstring": ast.get_docstring(tree),
            "comments": [],
            "content": content
        }
        # AST结构分析
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    "name": node.name,
                    "lineno": node.lineno,
                    "args": [a.arg for a in node.args.args],
                    "docstring": ast.get_docstring(node)
                }
                file_info["functions"].append(func_info)
            elif isinstance(node, ast.ClassDef):
                class_info = {
                    "name": node.name,
                    "lineno": node.lineno,
                    "docstring": ast.get_docstring(node),
                    "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                }
                file_info["classes"].append(class_info)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                file_info["imports"].append(ast.unparse(node))
            elif isinstance(node, ast.Assign):
                # 全局变量
                if isinstance(getattr(node, 'parent', None), ast.Module):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            file_info["globals"].append({"name": t.id, "lineno": node.lineno})
        # 注释提取（简单实现：以#开头的行）
        file_info["comments"] = [line.strip() for line in content.splitlines() if line.strip().startswith('#')]
        return file_info