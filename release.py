#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动版本发布脚本
用于管理版本号、提交代码、推送到 GitHub 并通知飞书
"""

import json
import subprocess
import sys
import os
from datetime import datetime
import requests

# 飞书 Webhook URL
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/67d21b26-439b-4b8b-92a9-39dad44392cf"

# 版本文件
VERSION_FILE = "VERSION"


def run_command(cmd, check=True):
    """运行命令并返回输出"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"❌ 命令执行失败: {cmd}")
        print(f"错误: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip()


def get_current_version():
    """获取当前版本号"""
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r') as f:
            return f.read().strip()
    return "0.0.0"


def increment_version(version, bump_type='patch'):
    """递增版本号"""
    major, minor, patch = map(int, version.split('.'))

    if bump_type == 'major':
        major += 1
        minor = 0
        patch = 0
    elif bump_type == 'minor':
        minor += 1
        patch = 0
    else:  # patch
        patch += 1

    return f"{major}.{minor}.{patch}"


def save_version(version):
    """保存版本号"""
    with open(VERSION_FILE, 'w') as f:
        f.write(version)


def get_git_changes():
    """获取 git 变更信息"""
    # 获取变更的文件
    changed_files = run_command("git diff --cached --name-only", check=False)

    # 获取变更统计
    stats = run_command("git diff --cached --stat", check=False)

    return {
        "files": changed_files.split('\n') if changed_files else [],
        "stats": stats
    }


def send_feishu_notification(version, message, changes, git_info):
    """发送飞书通知"""

    # 构建变更文件列表
    files_text = "\n".join([f"  • {f}" for f in changes['files'][:10]])
    if len(changes['files']) > 10:
        files_text += f"\n  ... 还有 {len(changes['files']) - 10} 个文件"

    content = f"""📦 飞书 Claude Bot 版本更新

🏷️ 版本号：v{version}
📅 发布时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📝 更新内容：
{message}

📂 变更文件：
{files_text if files_text else '  无'}

🔧 Git 操作：
  • Commit: {git_info['commit_hash']}
  • Branch: {git_info['branch']}
  • Remote: {git_info['remote']}

🔗 查看详情：{git_info['repo_url']}
"""

    payload = {
        "msg_type": "text",
        "content": {
            "text": content
        }
    }

    try:
        response = requests.post(FEISHU_WEBHOOK, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ 飞书通知发送成功")
        else:
            print(f"⚠️ 飞书通知发送失败: {response.status_code}")
    except Exception as e:
        print(f"⚠️ 飞书通知发送异常: {e}")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 release.py <更新说明> [版本类型: major|minor|patch]")
        print("示例: python3 release.py '添加会话管理功能' minor")
        sys.exit(1)

    message = sys.argv[1]
    bump_type = sys.argv[2] if len(sys.argv) > 2 else 'patch'

    if bump_type not in ['major', 'minor', 'patch']:
        print("❌ 版本类型必须是 major, minor 或 patch")
        sys.exit(1)

    print("=" * 50)
    print("🚀 开始发布流程")
    print("=" * 50)

    # 1. 检查是否有未提交的更改
    status = run_command("git status --porcelain", check=False)
    if not status:
        print("⚠️ 没有需要提交的更改")
        sys.exit(0)

    # 2. 获取当前版本并递增
    current_version = get_current_version()
    new_version = increment_version(current_version, bump_type)
    print(f"📌 版本: {current_version} → {new_version}")

    # 3. 保存新版本号
    save_version(new_version)

    # 4. 添加所有更改
    print("📦 添加文件到暂存区...")
    run_command("git add .")

    # 5. 获取变更信息
    changes = get_git_changes()

    # 6. 提交
    commit_message = f"v{new_version}: {message}"
    print(f"💾 提交: {commit_message}")
    run_command(f'git commit -m "{commit_message}"')

    # 7. 创建标签
    print(f"🏷️ 创建标签: v{new_version}")
    run_command(f'git tag -a v{new_version} -m "{message}"')

    # 8. 推送到远程
    print("⬆️ 推送到 GitHub...")
    branch = run_command("git branch --show-current")
    run_command(f"git push origin {branch}")
    run_command(f"git push origin v{new_version}")

    # 9. 获取 git 信息
    commit_hash = run_command("git rev-parse --short HEAD")
    remote_url = run_command("git config --get remote.origin.url")

    # 转换 SSH URL 为 HTTPS URL
    if remote_url.startswith("git@github.com:"):
        repo_url = remote_url.replace("git@github.com:", "https://github.com/").replace(".git", "")
    else:
        repo_url = remote_url.replace(".git", "")

    git_info = {
        "commit_hash": commit_hash,
        "branch": branch,
        "remote": remote_url,
        "repo_url": repo_url
    }

    # 10. 发送飞书通知
    print("📢 发送飞书通知...")
    send_feishu_notification(new_version, message, changes, git_info)

    print("=" * 50)
    print(f"✅ 发布完成！版本: v{new_version}")
    print("=" * 50)


if __name__ == "__main__":
    main()
