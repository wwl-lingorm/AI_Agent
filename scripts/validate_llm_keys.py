import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so `src` can be imported when running this script directly
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.utils.multi_llm_service import MultiLLMService


def mask_key(k: str) -> str:
    if not k:
        return None
    if len(k) <= 8:
        return k[:2] + '****' + k[-2:]
    return k[:4] + '****' + k[-4:]


def main():
    # 如果存在 .env 文件，先加载它（不会写回系统，只在当前进程生效）
    repo_root = Path(__file__).resolve().parents[1]
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
                    # 仅在未设置时注入，避免覆盖真实环境
                    if not os.getenv(k):
                        os.environ[k] = v
        except Exception as e:
            print(f"加载 .env 文件出错: {e}")

    env_vars = [
        'DEEPSEEK_API_KEY',
        'OPENAI_API_KEY',
        'OPENAI_BASE_URL',
        'TONGYI_API_KEY'
    ]
    print('检查环境变量（key 会被掩码显示，若为 None 表示未设置）:')
    for v in env_vars:
        val = os.getenv(v)
        print(f"- {v}: {mask_key(val) if val else None}")

    svc = MultiLLMService()
    providers = svc.get_available_providers()
    if providers:
        print('\n检测到已配置的 LLM 提供商:')
        for p in providers:
            print(f"- {p.value}")
    else:
        print('\n未检测到任何可用的 LLM 提供商（请设置 DEEPSEEK_API_KEY、OPENAI_API_KEY 或 TONGYI_API_KEY）')


if __name__ == '__main__':
    main()
