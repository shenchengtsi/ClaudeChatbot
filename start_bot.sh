#!/bin/bash
# 飞书 Claude Bot 启动脚本（异步版本）

cd /Users/samsonchoi/Desktop/AI_Workspace/feishu-claude-bot

# 清除 CLAUDECODE 环境变量，避免嵌套执行问题
unset CLAUDECODE

/Users/samsonchoi/Desktop/AI_Workspace/feishu-claude-bot/venv/bin/python bot_v3_async.py > /tmp/bot_v3_console.log 2>&1 &

echo "Bot 已在后台启动（异步版本）"
echo "查看日志: tail -f /Users/samsonchoi/Desktop/AI_Workspace/feishu-claude-bot/bot.log"
echo "查看进程: ps aux | grep 'python.*bot'"
