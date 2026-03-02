#!/bin/bash
# 停止飞书 Claude Bot

PID=$(ps aux | grep "python.*bot_v3_async.py" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    # 尝试查找其他版本
    PID=$(ps aux | grep "python.*bot" | grep -v grep | awk '{print $2}')
fi

if [ -z "$PID" ]; then
    echo "Bot 未运行"
else
    kill $PID
    echo "Bot 已停止 (PID: $PID)"
fi
