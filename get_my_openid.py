#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取你的飞书 Open ID
运行此脚本后，在飞书给机器人发任意消息，
终端会打印出你的 Open ID，复制到 config.py 中即可
"""

import json
import sys
import lark_oapi as lark

from config import APP_ID, APP_SECRET


def handle_message(data):
    raw = data.to_dict() if hasattr(data, 'to_dict') else data
    event = raw.get("event", {})
    sender = event.get("sender", {})
    message = event.get("message", {})

    open_id = sender.get("sender_id", {}).get("open_id", "")
    content = json.loads(message.get("content", "{}"))
    text = content.get("text", "")

    print("\n" + "=" * 50)
    print(f"✅ 收到消息！")
    print(f"📌 你的 Open ID 是：\n\n  {open_id}\n")
    print(f"💬 消息内容：{text}")
    print("=" * 50)
    print("\n请将上面的 Open ID 复制到 config.py 的 ALLOWED_OPEN_IDS 列表中")
    print("然后重新运行 python3 bot.py 即可\n")


def main():
    print("=" * 50)
    print("🔍 Open ID 获取工具")
    print("=" * 50)
    print(f"App ID: {APP_ID[:8]}...")
    print("\n⏳ 等待中...")
    print("👉 请在飞书中给机器人发送任意消息（如「你好」）")
    print("=" * 50 + "\n")

    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(handle_message) \
        .build()

    ws_client = lark.ws.Client(
        APP_ID,
        APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.ERROR
    )

    ws_client.start()


if __name__ == "__main__":
    main()
