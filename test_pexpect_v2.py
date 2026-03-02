#!/usr/bin/env python3
"""
使用 pexpect 测试 Claude Code 交互
"""

import pexpect
import sys
import time
import os

# 设置环境变量
env = {**os.environ, "CLAUDECODE": ""}

print("启动 Claude Code...")
child = pexpect.spawn(
    '/Users/samsonchoi/.local/bin/claude',
    ['--dangerously-skip-permissions'],
    env=env,
    cwd=os.path.expanduser("~/Desktop"),
    encoding='utf-8',
    timeout=120
)

# 将输出同时打印到屏幕
child.logfile_read = sys.stdout

try:
    # 等待并处理第一个提示（可能是 trust folder 或 bypass permissions）
    print("\n=== 等待安全提示 ===")
    index = child.expect(['accept', 'trust', pexpect.TIMEOUT], timeout=10)

    if index == 0:  # accept
        print("\n=== 检测到 accept 提示，发送 2 ===")
        child.sendline('2')
    elif index == 1:  # trust
        print("\n=== 检测到 trust 提示，发送 Enter ===")
        child.sendline('')
        # 尝试等待第二个提示，但如果没有也继续
        try:
            child.expect('accept', timeout=3)
            print("\n=== 检测到 accept 提示，发送 2 ===")
            child.sendline('2')
        except pexpect.TIMEOUT:
            print("\n=== 没有 accept 提示，直接继续 ===")

    # 等待 Claude Code 启动完成
    print("\n=== 等待 Claude Code 启动完成 ===")
    time.sleep(8)

    # 发送问题
    print("\n=== 发送问题: 1+1等于几 ===")
    child.sendline('1+1等于几')

    # 等待响应
    print("\n=== 等待响应（最多30秒）===")
    time.sleep(30)

    # 发送退出命令
    print("\n=== 发送退出命令 ===")
    child.sendline('exit')

    # 等待进程结束
    child.expect(pexpect.EOF, timeout=10)
    print("\n=== Claude Code 已退出 ===")

except pexpect.TIMEOUT as e:
    print(f"\n=== 超时: {e} ===")
    print(f"当前缓冲区内容: {child.before}")
except pexpect.EOF as e:
    print(f"\n=== 进程意外结束: {e} ===")
except Exception as e:
    print(f"\n=== 错误: {e} ===")
finally:
    if child.isalive():
        child.close(force=True)
    print("\n=== 测试完成 ===")
