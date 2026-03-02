#!/bin/bash

cd "$(dirname "$0")"

# 停止旧进程
pkill -f "bot_v4_streaming.py" 2>/dev/null

# 使用 env -i 创建干净环境
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
  /Users/samsonchoi/Desktop/AI_Workspace/feishu-claude-bot/bot_v4_streaming.py \
  > /tmp/bot_streaming_console.log 2>&1 &

echo "Bot 已在后台启动（流式版本）"
echo "查看日志: tail -f /Users/samsonchoi/Desktop/AI_Workspace/feishu-claude-bot/bot.log"
echo "查看进程: ps aux | grep 'python.*bot_v4_streaming'"
