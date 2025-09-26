# 测试文件 - 包含一些故意的代码问题
import os
import sys

def divide_numbers(a, b):
    # 没有处理除零错误
    return a / b

def unused_function():
    # 这个函数从未被调用
    x = 10
    y = 20
    return x + y

class TestClass:
    def __init__(self, name):
        self.name = name
    
    def get_name(self):
        return self.name
    
    def process_data(self, data):
        # 没有验证输入参数
        result = []
        for item in data:
            if item > 0:
                result.append(item * 2)
        return result

# 全局变量使用不当
GLOBAL_VAR = "test"

def main():
    # 使用硬编码的文件路径
    file_path = "C:\\hardcoded\\path\\file.txt"
    
    # 没有异常处理的文件操作
    with open(file_path, 'r') as f:
        content = f.read()
    
    # 可能的除零错误
    result = divide_numbers(10, 0)
    
    # 未使用的变量
    unused_var = "not used"
    
    return result

if __name__ == "__main__":
    main()