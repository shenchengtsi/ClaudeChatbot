#!/bin/bash
# 获取你的飞书 Open ID

cd "$(dirname "$0")"
source venv/bin/activate
python3 get_my_openid.py
