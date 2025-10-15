from .base_agent import BaseAgent
from src.utils.multi_llm_service import MultiLLMService, LLMProvider
from typing import Dict, Any

class RepairAgent(BaseAgent):
    def __init__(self, multi_llm_service: MultiLLMService):
        super().__init__("RepairAgent", "负责生成和执行代码修复方案")
        self.llm_service = multi_llm_service
    
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        self.log("开始批量文件修复/动态错误检测")
        use_langchain = task.get("use_langchain", False)
        code_context_map = task.get("code_context_map")
        all_issues = task.get("all_issues")
        preferred_model = task.get("preferred_model", "deepseek")
        provider_map = {
            "deepseek": LLMProvider.DEEPSEEK,
            "openai": LLMProvider.OPENAI,
            "tongyi": LLMProvider.TONGYI
        }
        preferred_provider = provider_map.get(preferred_model, LLMProvider.DEEPSEEK)

        if code_context_map is None or not isinstance(code_context_map, dict):
            return {"status": "error", "error": "缺少 code_context_map 或格式错误", "repair_results": []}

        # 兼容单文件 all_issues 结构
        if all_issues is None:
            all_issues = {}
        if isinstance(all_issues, list):
            if len(code_context_map) == 1:
                file_path = list(code_context_map.keys())[0]
                all_issues = {file_path: all_issues}
            else:
                return {"status": "error", "error": "all_issues为list但有多个文件，无法对应", "repair_results": []}

        import asyncio, os
        MAX_PROMPT_LEN = 3500  # token近似，防止超长
        async def repair_one_file(file_path, code, issues):
            issues_text = "\n".join([self._format_issue(issue) for issue in issues])
            # 自动切分超长代码
            if len(code) > MAX_PROMPT_LEN:
                self.log(f"文件 {file_path} 代码过长，自动切分修复")
                code_chunks = [code[i:i+MAX_PROMPT_LEN] for i in range(0, len(code), MAX_PROMPT_LEN)]
            else:
                code_chunks = [code]
            chunk_results = []
            for idx, chunk in enumerate(code_chunks):
                # 扩展静态问题类型
                prompt = f"请修复以下Python代码中的所有问题，并给出修复后的完整代码：\n\n问题列表：\n{issues_text}\n\n原始代码（第{idx+1}段）：\n{chunk}\n\n补充要求：\n1. 修复所有类型/语义/安全/风格/依赖/环境/性能/文档相关问题。\n2. 检查类型注解、异常处理、硬编码、依赖声明、环境变量、性能瓶颈、docstring、命名规范、代码重复、资源泄漏等。\n3. 按PEP8规范优化代码风格，补全注释和文档字符串。\n4. 检查并修复SQL注入、命令注入、未关闭文件、未处理异常等安全问题。\n5. 优化复杂度、消除死代码、提升可维护性。\n6. 检查依赖和环境变量声明，修复相关问题。\n7. 检查并补全类型注解。\n8. 优化性能（如循环、IO、内存占用）。\n9. 兼容Python2/3差异。\n10. 代码修复后需能通过静态分析和自动化测试。"
                self.log(f"修复文件: {file_path}, 段: {idx+1}/{len(code_chunks)}, prompt长度: {len(prompt)} 字符")
                try:
                    llm_result = await self.llm_service.generate_with_fallback(
                        prompt,
                        preferred_provider=preferred_provider,
                        max_tokens=2048,
                        temperature=0.3
                    )
                    if llm_result["success"]:
                        chunk_results.append(llm_result["content"])
                    else:
                        chunk_results.append(f"# 修复失败: {llm_result['error']}")
                except Exception as e:
                    chunk_results.append(f"# LLM修复异常: {str(e)}")
            fixed_code = "\n".join(chunk_results)
            return {
                "status": "completed" if all(not r.startswith("# 修复失败") for r in chunk_results) else "partial",
                "file": file_path,
                "fix_suggestion": fixed_code,
                "model_used": preferred_model,
                "issues": issues,
                "code_before": code,
                "code_after": fixed_code
            }

        # 动态错误检测与修复（pytest集成）
        async def detect_and_repair_runtime(file_path, code):
            import tempfile, subprocess, traceback, ast, importlib.util, sys
            with tempfile.NamedTemporaryFile('w', delete=False, suffix='.py') as f:
                f.write(code)
                temp_path = f.name

            # 预扫描 import，收集顶级模块名
            missing_stubs = set()
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for n in node.names:
                            name = n.name.split('.')[0]
                            if importlib.util.find_spec(name) is None:
                                missing_stubs.add(name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            name = node.module.split('.')[0]
                            if importlib.util.find_spec(name) is None:
                                missing_stubs.add(name)
            except Exception:
                # 如果 AST 解析出错，则继续后面的正常流程
                missing_stubs = set()

            stub_dir = None
            env = os.environ.copy()
            if missing_stubs:
                # 为缺失模块一次性生成 stub，避免多次重试
                import shutil
                # 通过 AST 收集缺失模块中具体引用的名称和属性，生成更有用的 stubs
                imported_names_map = {m: set() for m in missing_stubs}
                attr_usage_map = {m: set() for m in missing_stubs}
                try:
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ImportFrom):
                            if node.module:
                                root = node.module.split('.')[0]
                                if root in missing_stubs:
                                    for n in node.names:
                                        imported_names_map[root].add(n.name)
                        elif isinstance(node, ast.Attribute):
                            # 获取顶层名称
                            cur = node
                            while isinstance(cur.value, ast.Attribute):
                                cur = cur.value
                            if isinstance(cur.value, ast.Name):
                                top = cur.value.id
                                if top in missing_stubs:
                                    attr_usage_map[top].add(cur.attr)
                except Exception:
                    pass

                self.log(f"预检测到缺失模块: {missing_stubs}，将在运行前生成stubs以帮助动态检测")
                stub_dir = tempfile.mkdtemp(prefix='module_stubs_')
                try:
                    def write_stub(mod, target_dir, names=None, attrs=None):
                        names = names or set()
                        attrs = attrs or set()
                        mod_path = os.path.join(target_dir, f"{mod}.py")
                        with open(mod_path, 'w', encoding='utf-8') as sf:
                            sf.write('# auto-generated stub for missing module\n')
                            # 针对常见库 pygame，生成更丰富的stub
                            if mod == 'pygame':
                                sf.write('class Sprite:\n    pass\n\n')
                                sf.write('class Surface:\n    pass\n\n')
                                sf.write('def image_load(path):\n    return Surface()\n\n')
                                sf.write('class _Transform:\n    @staticmethod\n    def rotate(img, angle):\n        return img\n\n')
                                sf.write('image = type(\'image\', (), {\'load\': image_load})\n')
                                sf.write('transform = _Transform()\n')
                                sf.write('\ndef collide_circle_ratio(r):\n    def inner(a,b):\n        return False\n    return inner\n\n')
                                sf.write('class _SpriteModule:\n    Sprite = Sprite\n    collide_circle_ratio = staticmethod(collide_circle_ratio)\n\n')
                                sf.write('sprite = _SpriteModule()\n')
                            else:
                                # 导入的具体名字，生成占位类/函数
                                for nm in sorted(names):
                                    if nm and nm[0].isupper():
                                        sf.write(f'class {nm}:\n    pass\n\n')
                                    else:
                                        sf.write(f'def {nm}(*args, **kwargs):\n    return None\n\n')
                                # 模块属性访问，生成函数或占位对象
                                for at in sorted(attrs):
                                    if at:
                                        sf.write(f'{at} = None\n')
                    for mod in missing_stubs:
                        write_stub(mod, stub_dir, imported_names_map.get(mod), attr_usage_map.get(mod))
                    env['PYTHONPATH'] = stub_dir + os.pathsep + env.get('PYTHONPATH', '')
                    # 在当前进程中也插入 sys.path，方便 exec 使用
                    sys.path.insert(0, stub_dir)
                except Exception:
                    try:
                        shutil.rmtree(stub_dir)
                    except Exception:
                        pass
                    stub_dir = None

            try:
                # 扩展动态问题检测：支持pytest、unittest、性能分析、资源泄漏、环境变量缺失
                # 增加更长超时以捕获复杂运行时错误
                result = subprocess.run([
                    'pytest', temp_path, '--maxfail=1', '--disable-warnings', '--tb=long'
                ], capture_output=True, text=True, timeout=120, env=env)
                error_info = (result.stderr or '') + '\n' + (result.stdout or '')
                perf_info = ''
                # 性能分析（简单统计）
                try:
                    import time
                    start = time.time()
                    # 在受限全局命名空间中执行，捕获异常
                    exec_globals = {}
                    exec(code, exec_globals)
                    perf_info = f"执行耗时: {time.time()-start:.3f}s"
                except Exception as e:
                    perf_info += f"\n性能分析异常: {str(e)}\n{traceback.format_exc()}"

                # 如果 pytest 未捕获到其他错误，仍然尝试分析 stderr/stdout 中的 ModuleNotFoundError
                import re
                missing_from_output = set(re.findall(r"No module named '([A-Za-z0-9_]+)'", error_info))
                # 将两者合并（如果之前没有生成 stub，则后续会尝试生成）
                missing = missing_from_output
                if missing and not stub_dir:
                    # 在发现运行时缺失模块时，生成临时stubs并重试一次（后备）
                    self.log(f"检测到缺失模块: {missing}，尝试创建stub并重试测试")
                    import shutil
                    stub_dir = tempfile.mkdtemp(prefix='module_stubs_')
                    try:
                        for mod in missing:
                            mod_path = os.path.join(stub_dir, f"{mod}.py")
                            with open(mod_path, 'w', encoding='utf-8') as sf:
                                sf.write('# auto-generated stub for missing module\n')
                                sf.write('class _Stub: pass\n')
                                sf.write('\n')
                        env_retry = env.copy()
                        env_retry['PYTHONPATH'] = stub_dir + os.pathsep + env_retry.get('PYTHONPATH', '')
                        retry_result = subprocess.run([
                            'pytest', temp_path, '--maxfail=1', '--disable-warnings', '--tb=long'
                        ], capture_output=True, text=True, timeout=120, env=env_retry)
                        retry_error_info = (retry_result.stderr or '') + '\n' + (retry_result.stdout or '')
                        # 再次尝试exec在当前进程中加载stub
                        try:
                            sys.path.insert(0, stub_dir)
                            exec_globals = {}
                            exec(code, exec_globals)
                        except Exception as e2:
                            perf_info += f"\n重试执行异常: {str(e2)}\n{traceback.format_exc()}"
                        error_info += '\n---- retry with stubs output ----\n' + retry_error_info
                    finally:
                        try:
                            shutil.rmtree(stub_dir)
                        except Exception:
                            pass
                        stub_dir = None

                # 资源泄漏检测（文件未关闭、内存占用）
                resource_leak = ''
                if 'ResourceWarning' in error_info or '未关闭' in error_info:
                    resource_leak = '检测到资源泄漏（如文件未关闭）'
                # 环境变量缺失
                env_missing = ''
                if 'KeyError' in error_info and 'os.environ' in error_info:
                    env_missing = '检测到环境变量缺失'
                # 生成修复建议
                if result.returncode != 0 or resource_leak or env_missing:
                    prompt = f"以下是Python文件运行时错误traceback、性能分析、资源泄漏、环境变量缺失等信息，请分析并修复所有相关问题：\n\nTraceback及错误：\n{error_info}\n\n性能分析：{perf_info}\n资源泄漏：{resource_leak}\n环境变量：{env_missing}\n\n原始代码：\n{code}"
                    llm_result = await self.llm_service.generate_with_fallback(
                        prompt,
                        preferred_provider=preferred_provider,
                        max_tokens=2048,
                        temperature=0.3
                    )
                    fixed_code = llm_result["content"] if llm_result["success"] else code
                    return {
                        "status": "completed" if llm_result["success"] else "error",
                        "file": file_path,
                        "runtime_error": error_info,
                        "perf_info": perf_info,
                        "resource_leak": resource_leak,
                        "env_missing": env_missing,
                        "fix_suggestion": fixed_code,
                        "code_before": code,
                        "code_after": fixed_code
                    }
                else:
                    return {
                        "status": "completed",
                        "file": file_path,
                        "runtime_error": None,
                        "perf_info": perf_info,
                        "resource_leak": None,
                        "env_missing": None,
                        "fix_suggestion": code,
                        "code_before": code,
                        "code_after": code
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "file": file_path,
                    "runtime_error": str(e),
                    "fix_suggestion": code,
                    "code_before": code,
                    "code_after": code
                }
            finally:
                # 清理在当前进程中插入的 stub 路径
                try:
                    if stub_dir and stub_dir in sys.path:
                        sys.path.remove(stub_dir)
                except Exception:
                    pass

        # 并发修复所有文件（静态+动态）
        tasks = []
        for file_path, code in code_context_map.items():
            issues = all_issues.get(file_path, [])
            if not isinstance(issues, list):
                issues = []
            # 先静态修复，再动态检测
            tasks.append(repair_one_file(file_path, code, issues))
            tasks.append(detect_and_repair_runtime(file_path, code))

        repair_results = await asyncio.gather(*tasks)

        # 修复前后代码diff高亮（git风格）
        def code_diff_html(before, after):
            import difflib
            diff = difflib.ndiff(before.splitlines(), after.splitlines())
            html = []
            for line in diff:
                if line.startswith('+ '):
                    html.append(f'<span style="background:#e6ffed;color:#22863a;">{line}</span>')
                elif line.startswith('- '):
                    html.append(f'<span style="background:#ffeef0;color:#cb2431;">{line}</span>')
                elif line.startswith('? '):
                    continue
                else:
                    html.append(f'<span>{line}</span>')
            return '<br>'.join(html)

        # 汇总所有修复结果，区分静态/动态
        for r in repair_results:
            r['diff_html'] = code_diff_html(r.get('code_before',''), r.get('code_after',''))
            if r.get('runtime_error') or r.get('perf_info') or r.get('resource_leak') or r.get('env_missing'):
                r['result_type'] = 'dynamic'
            else:
                r['result_type'] = 'static'

        success_count = sum(1 for r in repair_results if r.get("status") == "completed")
        summary = f"批量修复+动态检测完成，成功: {success_count}，总任务: {len(repair_results)}"
        return {
            "status": "completed" if success_count == len(repair_results) else "partial",
            "repair_results": repair_results,
            "summary": summary
        }

    def _format_issue(self, issue: dict) -> str:
        """将结构化issue转为自然语言描述"""
        desc = f"文件: {issue.get('file')}, 行: {issue.get('line')}, 类型: {issue.get('type')}, 工具: {issue.get('tool')}\n问题: {issue.get('message')}"
        return desc
    
    def _build_repair_prompt(self, issue: str, code_context: str) -> str:
        """构建修复提示词"""
        return f"""
你是一个专业的代码修复AI助手。请分析以下代码问题并提供修复方案。

问题描述：
{issue}

相关代码：
```python
{code_context}
请按照以下步骤提供修复：

1.首先分析问题的根本原因

2.然后提供具体的修复方案说明

3.最后给出修复后的完整代码块

要求：

修复后的代码必须保持原有功能

代码风格要与原代码一致

添加必要的注释说明修复内容

确保没有引入新的问题

请直接给出修复后的完整代码：
"""