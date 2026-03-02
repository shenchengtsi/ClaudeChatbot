#!/bin/bash
# 停止飞书 Claude Bot

PID=$(ps aux | grep "python.*bot_v2.py" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "Bot 未运行"
else
    kill $PID
    echo "Bot 已停止 (PID: $PID)"
fi
