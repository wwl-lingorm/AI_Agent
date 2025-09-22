# [file name]: run_web.py
# [file content begin]
#!/usr/bin/env python3
"""
Web界面启动脚本
"""
import os
import sys

# 添加项目根目录和src目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

from web_app.main import web_interface

if __name__ == "__main__":
    print("启动多Agent缺陷检测系统Web界面...")
    print("访问地址: http://localhost:8000")
    web_interface.run(host="0.0.0.0", port=8000)
# [file content end]    