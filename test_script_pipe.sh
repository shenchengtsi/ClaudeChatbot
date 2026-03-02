#!/bin/bash
# 使用 script 命令记录完整的终端会话

export CLAUDECODE=""

# 创建临时文件
TYPESCRIPT="/tmp/claude_session_$(date +%s).txt"

echo "开始记录 Claude Code 会话到: $TYPESCRIPT"

# 使用 script 命令，并通过管道发送命令
(
    sleep 3
    echo ""  # 确认第一个提示
    sleep 2
    echo "2"  # 接受 Bypass Permissions
    sleep 5
    echo "1+1等于几"
    sleep 15
    echo "exit"
    sleep 2
) | script -q "$TYPESCRIPT" /Users/samsonchoi/.local/bin/claude --dangerously-skip-permissions

echo ""
echo "=========================================="
echo "会话记录内容:"
echo "=========================================="
cat "$TYPESCRIPT"
