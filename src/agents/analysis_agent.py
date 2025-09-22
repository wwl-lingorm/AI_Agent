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
            return {"status": "error", "error": "代码库路径无效"}
        
        # 分析代码结构
        analysis_result = self._analyze_code_structure(repo_path)
        
        return {
            "status": "completed",
            "files_analyzed": len(analysis_result.get("files", [])),
            "structure": analysis_result,
            "summary": "代码结构分析完成"
        }
    
    def _analyze_code_structure(self, repo_path: str) -> Dict[str, Any]:
        """分析代码结构"""
        result = {
            "files": [],
            "imports": [],
            "functions": [],
            "classes": []
        }
        
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 使用AST分析Python代码
                        tree = ast.parse(content)
                        file_info = self._analyze_python_file(tree, file_path)
                        result["files"].append(file_info)
                        
                    except Exception as e:
                        self.log(f"分析文件 {file_path} 时出错: {str(e)}", "error")
        
        return result
    
    def _analyze_python_file(self, tree, file_path: str) -> Dict[str, Any]:
        """分析单个Python文件"""
        file_info = {
            "path": file_path,
            "functions": [],
            "classes": [],
            "imports": []
        }
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                file_info["functions"].append({
                    "name": node.name,
                    "lineno": node.lineno
                })
            elif isinstance(node, ast.ClassDef):
                file_info["classes"].append({
                    "name": node.name, 
                    "lineno": node.lineno
                })
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                file_info["imports"].append(ast.unparse(node))
        
        return file_info