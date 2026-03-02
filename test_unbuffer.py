#!/usr/bin/env python3
"""
使用 pexpect 配合 unbuffer 测试 Claude Code 交互
unbuffer 可以让 Claude Code 认为它在真正的交互式终端中运行
"""

import pexpect
import sys
import time
import os
import re

# 设置环境变量
env = {**os.environ, "CLAUDECODE": ""}

print("使用 unbuffer 启动 Claude Code...")
child = pexpect.spawn(
    'unbuffer',
    ['-p', '/Users/samsonchoi/.local/bin/claude', '--dangerously-skip-permissions'],
    env=env,
    cwd=os.path.expanduser("~/Desktop"),
    encoding='utf-8',
    timeout=120
)

# 将输出同时打印到屏幕
child.logfile_read = sys.stdout

def clean_ansi(text):
    """移除 ANSI 控制字符"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

try:
    # 等待并处理安全提示
    print("\n=== 等待安全提示 ===")
    index = child.expect(['accept', 'trust', pexpect.TIMEOUT], timeout=15)

    if index == 0:  # accept
        print("\n=== 检测到 accept 提示，发送 2 ===")
        child.sendline('2')
    elif index == 1:  # trust
        print("\n=== 检测到 trust 提示，发送 Enter ===")
        child.sendline('')
        # 尝试等待第二个提示
        try:
            child.expect('accept', timeout=5)
            print("\n=== 检测到 accept 提示，发送 2 ===")
            child.sendline('2')
        except pexpect.TIMEOUT:
            print("\n=== 没有 accept 提示，直接继续 ===")

    # 等待 Claude Code 启动完成（等待提示符或欢迎信息）
    print("\n=== 等待 Claude Code 启动完成 ===")
    time.sleep(10)

    # 发送问题
    print("\n=== 发送问题: 1+1等于几 ===")
    child.sendline('1+1等于几')

    # 等待响应（使用更智能的方式）
    print("\n=== 等待响应 ===")
    response_lines = []
    idle_time = 0
    max_idle = 5  # 5秒无输出认为完成

    for i in range(60):  # 最多等待60秒
        try:
            line = child.readline()
            if line:
                response_lines.append(line)
                idle_time = 0
                print(f"[收到输出] {line.rstrip()}")
            else:
                idle_time += 1
                if idle_time >= max_idle:
                    print(f"\n=== {max_idle}秒无新输出，认为响应完成 ===")
                    break
                time.sleep(1)
        except:
            idle_time += 1
            if idle_time >= max_idle:
                print(f"\n=== {max_idle}秒无新输出，认为响应完成 ===")
                break
            time.sleep(1)

    # 打印收集到的响应
    print("\n" + "="*50)
    print("收集到的响应:")
    print("="*50)
    full_response = ''.join(response_lines)
    cleaned = clean_ansi(full_response)
    print(cleaned)
    print("="*50)

    # 发送退出命令
    print("\n=== 发送退出命令 ===")
    child.sendline('exit')

    # 等待进程结束
    try:
        child.expect(pexpect.EOF, timeout=10)
        print("\n=== Claude Code 已退出 ===")
    except:
        print("\n=== 强制关闭 ===")

except pexpect.TIMEOUT as e:
    print(f"\n=== 超时: {e} ===")
    print(f"当前缓冲区: {child.before[:500]}")
except pexpect.EOF as e:
    print(f"\n=== 进程意外结束 ===")
except Exception as e:
    print(f"\n=== 错误: {e} ===")
    import traceback
    traceback.print_exc()
finally:
    if child.isalive():
        child.close(force=True)
    print("\n=== 测试完成 ===")
