#!/bin/bash
# 飞书 Claude Bot 启动脚本

cd "$(dirname "$0")"
source venv/bin/activate
python3 bot.py
