#!/bin/bash
# 飞书 Claude Bot 启动脚本（完全干净的环境）

cd /Users/samsonchoi/Desktop/AI_Workspace/feishu-claude-bot

# 使用 env -i 创建一个完全干净的环境，只保留必要的变量
env -i \
  HOME=/Users/samsonchoi \
  PATH=/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:/Users/samsonchoi/.local/bin \
  SHELL=/bin/bash \
  USER=samsonchoi \
  LOGNAME=samsonchoi \
  HTTP_PROXY=http://127.0.0.1:7890 \
  HTTPS_PROXY=http://127.0.0.1:7890 \
  ALL_PROXY=http://127.0.0.1:7890 \
  ANTHROPIC_BASE_URL=https://gaccode.com/claudecode \
  ANTHROPIC_API_KEY=sk-ant-oat01-621001787429909d196f476abaf986909a08c1b19bf7649df4acbef36b5e495c \
  /Users/samsonchoi/Desktop/AI_Workspace/feishu-claude-bot/venv/bin/python \
  /Users/samsonchoi/Desktop/AI_Workspace/feishu-claude-bot/bot_v3_async.py \
  > /tmp/bot_v3_console.log 2>&1 &

echo "Bot 已在后台启动（干净环境）"
echo "查看日志: tail -f /Users/samsonchoi/Desktop/AI_Workspace/feishu-claude-bot/bot.log"
echo "查看进程: ps aux | grep 'python.*bot'"
