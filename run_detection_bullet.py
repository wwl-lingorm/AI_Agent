import asyncio
from src.agents.detection_agent import DetectionAgent

async def main():
    agent = DetectionAgent()
    res = await agent.execute({'repo_path': r'fishgame-master\\bullet.py'})
    import json
    print(json.dumps(res, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    asyncio.run(main())
