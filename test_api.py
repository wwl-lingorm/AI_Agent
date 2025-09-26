import requests
import json
import time

# 测试分析API
url = "http://localhost:8000/api/tasks/analyze"
data = {
    "repo_path": "c:\\Users\\23876\\Desktop\\AI_agent\\test_sample.py",
    "preferred_model": "deepseek"
}

print("发送分析请求...")
response = requests.post(url, json=data)
print(f"响应状态码: {response.status_code}")
print(f"响应内容: {response.json()}")

if response.status_code == 200:
    task_id = response.json().get("task_id")
    print(f"任务ID: {task_id}")
    
    # 等待任务完成并检查结果
    time.sleep(5)
    
    result_url = f"http://localhost:8000/api/tasks/{task_id}"
    result_response = requests.get(result_url)
    print(f"任务结果: {json.dumps(result_response.json(), indent=2, ensure_ascii=False)}")