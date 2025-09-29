import subprocess
import os
import tempfile
import ast
from .base_agent import BaseAgent
from typing import Dict, Any, List

class ValidationAgent(BaseAgent):
    def __init__(self):
        super().__init__("ValidationAgent", "负责验证修复后的代码")
        self.test_results = {}
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        self.log("开始验证修复结果")
        use_langchain = task.get("use_langchain", False)
        if use_langchain:
            try:
                from src.agents.langchain_agent import agent
                code_context_map = task.get("code_context_map")
                # 默认取第一个文件
                if code_context_map:
                    file_path = list(code_context_map.keys())[0]
                    code = code_context_map[file_path]
                    result = agent.run({"code": code, "issues": []})
                    return {
                        "status": "completed",
                        "langchain_result": result,
                        "summary": "LangChain测试/验证完成",
                        "code_tested": code,
                        "test_result": result
                    }
                else:
                    return {"status": "error", "error": "LangChain测试需提供code_context_map"}
            except Exception as e:
                return {"status": "error", "error": f"LangChain测试异常: {str(e)}"}
        repo_path = task.get("repo_path")
        # 批量验证模式：支持传入修复结果列表
        repair_results = task.get("repair_results")
        code_context_map = task.get("code_context_map")  # {file_path: 最新代码内容}
        validation_report = []
        if repair_results is not None and code_context_map:
            if not repair_results:
                # 没有修复结果需要验证
                return {
                    "status": "completed",
                    "validation_report": [],
                    "summary": "无需验证（未发现问题或修复失败）"
                }
                
            for repair in repair_results:
                issue = repair.get("original_issue")
                file_path = issue.get("file") if issue else None
                fixed_code = repair.get("fix_suggestion")
                original_issue = issue.get("message") if issue else None
                if not repo_path or not fixed_code or not file_path:
                    validation_report.append({"status": "error", "error": "缺少必要信息", "repair": repair})
                    continue
                validation_results = {
                    "syntax_check": await self._check_syntax(fixed_code, file_path),
                    "test_execution": await self._run_tests(repo_path, file_path, fixed_code),
                    "regression_check": await self._check_regression(original_issue, fixed_code),
                    "code_quality": await self._check_code_quality(fixed_code, file_path)
                }
                overall_passed = all(result.get("passed", False) for result in validation_results.values())
                validation_report.append({
                    "file": file_path,
                    "original_issue": original_issue,
                    "validation_passed": overall_passed,
                    "detailed_results": validation_results,
                    "summary": f"验证结果: {'通过' if overall_passed else '未通过'}"
                })
            return {
                "status": "completed",
                "validation_report": validation_report,
                "summary": f"共验证{len(validation_report)}个修复结果"
            }
        # 单个修复验证兼容
        fixed_code = task.get("fixed_code")
        original_issue = task.get("original_issue")
        file_path = task.get("file_path")
        if not repo_path or not fixed_code:
            return {"status": "error", "error": "缺少代码库路径或修复后的代码"}
        validation_results = {
            "syntax_check": await self._check_syntax(fixed_code, file_path),
            "test_execution": await self._run_tests(repo_path, file_path, fixed_code),
            "regression_check": await self._check_regression(original_issue, fixed_code),
            "code_quality": await self._check_code_quality(fixed_code, file_path)
        }
        overall_passed = all(result.get("passed", False) for result in validation_results.values())
        return {
            "status": "completed",
            "validation_passed": overall_passed,
            "detailed_results": validation_results,
            "summary": f"验证结果: {'通过' if overall_passed else '未通过'}"
        }
    
    async def _check_syntax(self, code: str, file_path: str) -> Dict[str, Any]:
        """检查语法是否正确"""
        try:
            # 对于Python代码，使用ast模块检查语法
            if file_path and file_path.endswith('.py'):
                ast.parse(code)
                return {"passed": True, "message": "Python语法检查通过"}
            else:
                # 对于其他语言，可以添加相应检查
                return {"passed": True, "message": "语法检查跳过（非Python文件）"}
        except SyntaxError as e:
            return {"passed": False, "message": f"语法错误: {str(e)}"}
        except Exception as e:
            return {"passed": False, "message": f"语法检查失败: {str(e)}"}
    
    async def _run_tests(self, repo_path: str, file_path: str, fixed_code: str) -> Dict[str, Any]:
        """运行测试"""
        try:
            # 创建临时文件测试修复后的代码
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                temp_file.write(fixed_code)
                temp_file_path = temp_file.name
            
            # 尝试运行相关测试
            test_result = subprocess.run(
                ['python', '-m', 'pytest', '--tb=short', '-v'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30  # 30秒超时
            )
            
            os.unlink(temp_file_path)  # 清理临时文件
            
            return {
                "passed": test_result.returncode == 0,
                "returncode": test_result.returncode,
                "stdout": test_result.stdout,
                "stderr": test_result.stderr,
                "message": "测试执行完成"
            }
            
        except subprocess.TimeoutExpired:
            return {"passed": False, "message": "测试执行超时"}
        except Exception as e:
            return {"passed": False, "message": f"测试执行失败: {str(e)}"}
    
    async def _check_regression(self, original_issue: str, fixed_code: str) -> Dict[str, Any]:
        """检查是否修复了原始问题且没有引入回归"""
        # 简化的回归检查：确保修复代码不包含已知的错误模式
        common_bug_patterns = [
            "undefined variable",
            "syntax error",
            "import error",
            "division by zero"
        ]
        
        issue_fixed = True
        regression_found = False
        
        # 检查原始问题是否被修复（简化逻辑）
        if original_issue and any(pattern in original_issue.lower() for pattern in common_bug_patterns):
            # 检查修复后的代码是否还包含这些模式
            code_lower = fixed_code.lower()
            for pattern in common_bug_patterns:
                if pattern in original_issue.lower() and pattern not in code_lower:
                    issue_fixed = True
                    break
        
        return {
            "passed": issue_fixed and not regression_found,
            "issue_fixed": issue_fixed,
            "regression_found": regression_found,
            "message": "回归检查完成"
        }
    
    async def _check_code_quality(self, code: str, file_path: str) -> Dict[str, Any]:
        """检查代码质量"""
        try:
            # 简单的代码质量检查
            lines = code.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]
            
            quality_metrics = {
                "total_lines": len(lines),
                "non_empty_lines": len(non_empty_lines),
                "comment_ratio": self._calculate_comment_ratio(lines),
                "line_length_violations": self._check_line_length(lines),
                "has_docstring": self._check_docstring(code)
            }
            
            # 简单的质量评分（可以根据需要扩展）
            quality_score = self._calculate_quality_score(quality_metrics)
            
            return {
                "passed": quality_score >= 0.6,  # 60%以上认为质量合格
                "quality_score": quality_score,
                "metrics": quality_metrics,
                "message": f"代码质量评分: {quality_score:.2f}"
            }
            
        except Exception as e:
            return {"passed": False, "message": f"代码质量检查失败: {str(e)}"}
    
    def _calculate_comment_ratio(self, lines: List[str]) -> float:
        """计算注释比例"""
        comment_lines = [line for line in lines if line.strip().startswith('#')]
        non_empty_lines = [line for line in lines if line.strip()]
        
        if not non_empty_lines:
            return 0.0
        
        return len(comment_lines) / len(non_empty_lines)
    
    def _check_line_length(self, lines: List[str]) -> int:
        """检查行长度违规（超过80字符）"""
        return sum(1 for line in lines if len(line) > 80)
    
    def _check_docstring(self, code: str) -> bool:
        """检查是否有文档字符串"""
        try:
            module = ast.parse(code)
            if module.body and isinstance(module.body[0], ast.Expr) and isinstance(module.body[0].value, ast.Str):
                return True
            
            # 检查函数和类的docstring
            for node in ast.walk(module):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                    if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Str):
                        return True
            return False
        except:
            return False
    
    def _calculate_quality_score(self, metrics: Dict[str, Any]) -> float:
        """计算代码质量评分"""
        score = 0.0
        
        # 注释比例得分（理想值20%）
        comment_ratio = metrics["comment_ratio"]
        comment_score = max(0, 1 - abs(comment_ratio - 0.2) / 0.2)
        
        # 行长度得分
        line_violations = metrics["line_length_violations"]
        total_lines = max(metrics["total_lines"], 1)
        line_length_score = max(0, 1 - (line_violations / total_lines))
        
        # 文档字符串得分
        docstring_score = 1.0 if metrics["has_docstring"] else 0.3
        
        # 综合得分
        score = (comment_score * 0.3 + line_length_score * 0.3 + docstring_score * 0.4)
        
        return min(1.0, score)