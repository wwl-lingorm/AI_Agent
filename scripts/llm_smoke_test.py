import asyncio
import os
from pathlib import Path
import sys
# ensure repo root
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.utils.multi_llm_service import MultiLLMService, LLMProvider

async def test_provider(svc: MultiLLMService, provider: LLMProvider):
    prompt = "请用一句话返回 OK，用中文。"
    try:
        res = await svc.generate_with_fallback(prompt, preferred_provider=provider, max_tokens=60, temperature=0.0)
        return provider.value, res
    except Exception as e:
        return provider.value, {"success": False, "error": str(e)}

async def main():
    # Load .env from repo root if present (do not overwrite existing env vars)
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
                    if not os.getenv(k):
                        os.environ[k] = v
        except Exception as e:
            print(f"加载 .env 文件出错: {e}")

    svc = MultiLLMService()
    providers = svc.get_available_providers()
    if not providers:
        print('未检测到任何 LLM 提供商（请检查 env keys）')
        return
    print('检测到提供商:', [p.value for p in providers])
    results = []
    for p in providers:
        print(f'正在测试: {p.value}')
        r = await test_provider(svc, p)
        results.append(r)
    print('\n测试结果:')
    for name, out in results:
        print('---')
        print('提供商:', name)
        if isinstance(out, dict):
            if out.get('success'):
                content = out.get('content')
                snippet = content.replace('\n', ' ')[:500]
                print('成功: (内容片段) ', snippet)
            else:
                print('失败: ', out.get('error'))
                print('内容: ', out.get('content'))
        else:
            print('返回: ', out)

if __name__ == '__main__':
    asyncio.run(main())
