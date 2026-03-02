#!/usr/bin/env python3
"""
测试使用 script 命令来捕获 Claude Code 的交互式输出
script 命令会创建一个真实的 typescript 会话
"""

import subprocess
import tempfile
import time
import os

# 创建临时文件存储 typescript
with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as f:
    typescript_file = f.name

print(f"Typescript 文件: {typescript_file}")

# 使用 script 命令启动 Claude Code
# -q: 安静模式，不输出启动/结束消息
# -F: 立即刷新输出
env = {**os.environ, "CLAUDECODE": ""}

# 创建一个临时脚本来运行 Claude Code 并发送命令
script_content = f"""#!/bin/bash
/Users/samsonchoi/.local/bin/claude --dangerously-skip-permissions <<EOF
1+1等于几
exit
EOF
"""

with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
    script_file = f.name
    f.write(script_content)

os.chmod(script_file, 0o755)

try:
    # 使用 script 命令运行
    result = subprocess.run(
        ['script', '-q', typescript_file, script_file],
        cwd=os.path.expanduser("~/Desktop"),
        env=env,
        timeout=30,
        capture_output=True,
        text=True
    )

    print(f"返回码: {result.returncode}")
    print(f"stdout: {result.stdout}")
    print(f"stderr: {result.stderr}")

    # 读取 typescript 文件
    time.sleep(1)
    with open(typescript_file, 'r') as f:
        output = f.read()

    print(f"\n{'='*50}")
    print(f"Typescript 内容 ({len(output)} 字符):")
    print(f"{'='*50}")
    print(output)

finally:
    # 清理临时文件
    if os.path.exists(typescript_file):
        os.unlink(typescript_file)
    if os.path.exists(script_file):
        os.unlink(script_file)
