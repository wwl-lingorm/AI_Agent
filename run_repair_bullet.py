import asyncio
import json
import os
import sys
from pathlib import Path
from src.agents.detection_agent import DetectionAgent
from src.agents.repair_agent import RepairAgent
from src.utils.multi_llm_service import MultiLLMService
import uuid
import datetime
import io
import zipfile


# Load .env from repo root if present (do not overwrite existing env vars)
repo_root = Path(__file__).resolve().parents[0]
dotenv_path = repo_root / '.env'
if dotenv_path.exists():
    try:
        with open(dotenv_path, 'r', encoding='utf-8') as df:
            for ln in df:
                ln = ln.strip()
                if not ln or ln.startswith('#'):
                    continue
                if '=' not in ln:
                    continue
                k, v = ln.split('=', 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if not os.getenv(k):
                    os.environ[k] = v
    except Exception as e:
        print(f"加载 .env 文件出错: {e}")


async def analyze_and_repair(target_path: str, preferred_model: str = 'deepseek'):
    """Analyze a single file or all .py files under a directory and attempt repairs.

    Outputs will be written to ./repair_outputs/<timestamp>/. A zip of fixed files is also produced.
    """
    det = DetectionAgent()
    multi = MultiLLMService()
    repair_agent = RepairAgent(multi)

    p = Path(target_path)
    if not p.exists():
        raise FileNotFoundError(f"目标路径不存在: {target_path}")

    # collect python files
    py_files = []
    if p.is_file() and p.suffix == '.py':
        py_files = [p]
    elif p.is_dir():
        ignore_dirs = {'.venv', 'venv', '__pycache__', 'node_modules', '.git'}
        ignore_exts = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.bin', '.dat', '.exe', '.dll'}
        for root, dirs, files in os.walk(p):
            # modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for f in files:
                fp = Path(root) / f
                if fp.suffix.lower() in ignore_exts:
                    continue
                if f.endswith('.py'):
                    # skip generated files in virtualenvs etc.
                    if any(part in ignore_dirs for part in fp.parts):
                        continue
                    py_files.append(fp)
    else:
        raise ValueError("仅支持 Python 文件或目录")

    if not py_files:
        print("未找到任何 .py 文件，退出")
        return

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = repo_root / 'repair_outputs' / f'repair_{timestamp}_{uuid.uuid4().hex[:6]}'
    out_dir.mkdir(parents=True, exist_ok=True)

    overall_results = {}

    for file_path in py_files:
        rel = str(file_path.relative_to(repo_root)) if repo_root in file_path.parents else str(file_path)
        print(f"分析文件: {rel}")
        # run detection
        det_res = await det.execute({'repo_path': str(file_path)})
        all_issues = det_res.get('all_issues', [])
        high = [it for it in all_issues if any(k in (it.get('type') or '').lower() for k in ['error', 'warn', 'runtime', 'critical', 'fatal'])]

        # read source
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
        except Exception as e:
            print(f"读取文件失败 {file_path}: {e}")
            continue

        code_context_map = {rel: code}

        if not high:
            print(f"{rel} 未发现高优先级问题，跳过修复")
            overall_results[rel] = {'detection': det_res, 'repair': None}
            continue

        print(f"{rel} 发现 {len(high)} 个高优先级问题，调用 LLM 修复...")
        repair_res = await repair_agent.execute({
            'all_issues': high,
            'code_context_map': code_context_map,
            'preferred_model': preferred_model
        })

        # save outputs
        overall_results[rel] = {'detection': det_res, 'repair': repair_res}

        # if repair suggestions contain code_after, write to file(s)
        try:
            repair_results = None
            if isinstance(repair_res, dict):
                repair_results = repair_res.get('repair_results') or repair_res.get('results')
            if isinstance(repair_results, list):
                for i, rr in enumerate(repair_results):
                    if rr.get('code_after'):
                        # name patched file
                        fname = Path(rel).name
                        if len(repair_results) > 1:
                            fname = fname.replace('.py', f'_fix{i+1}.py')
                        out_path = out_dir / fname
                        with open(out_path, 'w', encoding='utf-8') as wf:
                            wf.write(rr['code_after'])
                        print(f"写入修复文件: {out_path}")
            elif isinstance(repair_res, dict) and repair_res.get('code_after'):
                out_path = out_dir / Path(rel).name
                with open(out_path, 'w', encoding='utf-8') as wf:
                    wf.write(repair_res['code_after'])
                print(f"写入修复文件: {out_path}")
        except Exception as e:
            print(f"保存修复结果出错: {e}")

    # write overall JSON
    summary_path = out_dir / 'repair_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as sf:
        json.dump(overall_results, sf, ensure_ascii=False, indent=2)

    # create zip of all fixed files
    zip_path = out_dir.with_suffix('.zip')
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for f in out_dir.iterdir():
            zf.write(f, arcname=f.name)

    print(f"修复输出保存在: {out_dir}")
    print(f"修复 zip: {zip_path}")


def _usage():
    print("用法: python run_repair_bullet.py <path-to-file-or-dir> [preferred_model]")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        _usage()
        sys.exit(1)
    target = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else 'deepseek'
    asyncio.run(analyze_and_repair(target, model))
