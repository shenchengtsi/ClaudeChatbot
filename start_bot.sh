#!/bin/bash
# 飞书 Claude Bot 启动脚本（新位置）

cd /Users/samsonchoi/Desktop/AI_Workspace/feishu-claude-bot
/Users/samsonchoi/Desktop/AI_Workspace/feishu-claude-bot/venv/bin/python bot_v2.py > /tmp/bot_v2_console.log 2>&1 &

echo "Bot 已在后台启动"
echo "查看日志: tail -f /Users/samsonchoi/Desktop/AI_Workspace/feishu-claude-bot/bot.log"
echo "查看进程: ps aux | grep 'python.*bot'"
