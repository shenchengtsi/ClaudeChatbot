#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书 Claude Bot - 流式版本
使用 Anthropic API + 飞书 Card Kit Streaming 实现实时流式输出
"""

import json
import threading
import logging
import os
import signal
import sys
import time
import uuid
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from anthropic import Anthropic

# ========== 加载配置 ==========
from config import APP_ID, APP_SECRET, ALLOWED_OPEN_IDS, WORK_DIR, MAX_OUTPUT_LEN

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)

# ========== 飞书客户端 ==========
feishu_client = lark.Client.builder() \
    .app_id(APP_ID) \
    .app_secret(APP_SECRET) \
    .build()

# ========== Anthropic 客户端 ==========
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "sk-ant-oat01-621001787429909d196f476abaf986909a08c1b19bf7649df4acbef36b5e495c")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://gaccode.com/claudecode")

anthropic_client = Anthropic(
    api_key=ANTHROPIC_API_KEY,
    base_url=ANTHROPIC_BASE_URL
)

# ========== 会话持久化目录 ==========
SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

# ========== 飞书 Card Kit Streaming ==========
class FeishuStreamingCard:
    """飞书流式卡片管理器"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = "https://open.feishu.cn/open-apis"
        self.token_cache = None
        self.token_expires_at = 0

    def get_token(self) -> str:
        """获取 tenant_access_token"""
        now = time.time()
        if self.token_cache and self.token_expires_at > now + 60:
            return self.token_cache

        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={
            "app_id": self.app_id,
            "app_secret": self.app_secret
        })
        data = resp.json()

        if data.get("code") != 0:
            raise Exception(f"获取 token 失败: {data.get('msg')}")

        self.token_cache = data["tenant_access_token"]
        self.token_expires_at = now + data.get("expire", 7200)
        return self.token_cache

    def create_card(self) -> Dict[str, str]:
        """创建流式卡片"""
        token = self.get_token()
        url = f"{self.base_url}/cardkit/v1/cards"

        card_json = {
            "schema": "2.0",
            "config": {
                "streaming_mode": True,
                "summary": {"content": "[正在生成...]"},
                "streaming_config": {
                    "print_frequency_ms": {"default": 100},
                    "print_step": {"default": 5}
                }
            },
            "body": {
                "elements": [{
                    "tag": "markdown",
                    "content": "⏳ 正在思考...",
                    "element_id": "content"
                }]
            }
        }

        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={"card": json.dumps(card_json)}
        )

        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"创建卡片失败: {data.get('msg')}")

        return {
            "card_id": data["data"]["card_id"],
            "sequence": 0
        }

    def send_card(self, chat_id: str, card_id: str, reply_to: Optional[str] = None) -> str:
        """发送卡片消息"""
        token = self.get_token()
        url = f"{self.base_url}/im/v1/messages"

        params = {"receive_id_type": "chat_id"}
        payload = {
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": json.dumps({"type": "template", "data": {"card_id": card_id}})
        }

        if reply_to:
            payload["reply_in_thread"] = False
            payload["uuid"] = str(uuid.uuid4())

        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            params=params,
            json=payload
        )

        data = resp.json()
        if data.get("code") != 0:
            raise Exception(f"发送卡片失败: {data.get('msg')}")

        return data["data"]["message_id"]

    def update_card(self, card_id: str, sequence: int, content: str) -> int:
        """更新卡片内容"""
        token = self.get_token()
        url = f"{self.base_url}/cardkit/v1/cards/{card_id}"

        card_json = {
            "schema": "2.0",
            "body": {
                "elements": [{
                    "tag": "markdown",
                    "content": content,
                    "element_id": "content"
                }]
            }
        }

        resp = requests.patch(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={
                "card": json.dumps(card_json),
                "sequence": sequence
            }
        )

        data = resp.json()
        if data.get("code") != 0:
            log.warning(f"更新卡片失败: {data.get('msg')}")
            return sequence

        return sequence + 1

# ========== 会话管理 ==========
class ChatSession:
    """聊天会话"""

    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.history = []
        self.history_file = SESSIONS_DIR / f"{chat_id}.json"
        self.load_history()

    def load_history(self):
        """加载历史记录"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = data.get("messages", [])
                    log.info(f"为 chat_id={self.chat_id} 加载了 {len(self.history)} 条历史记录")
            except Exception as e:
                log.error(f"加载历史记录失败: {e}")
                self.history = []

    def save_history(self):
        """保存历史记录"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({"messages": self.history}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"保存历史记录失败: {e}")

    def add_message(self, role: str, content: str):
        """添加消息到历史"""
        self.history.append({"role": role, "content": content})
        # 限制历史记录长度
        if len(self.history) > 20:
            self.history = self.history[-20:]
        self.save_history()

    def get_messages(self):
        """获取消息历史（Anthropic API 格式）"""
        return self.history.copy()

class SessionManager:
    """会话管理器"""

    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
        self.lock = threading.Lock()

    def get_session(self, chat_id: str) -> ChatSession:
        """获取或创建会话"""
        with self.lock:
            if chat_id not in self.sessions:
                self.sessions[chat_id] = ChatSession(chat_id)
                log.info(f"为 chat_id={chat_id} 创建新 session")
            return self.sessions[chat_id]

    def close_session(self, chat_id: str):
        """关闭会话"""
        with self.lock:
            if chat_id in self.sessions:
                del self.sessions[chat_id]
                log.info(f"关闭 chat_id={chat_id} 的 session")

# ========== 全局实例 ==========
session_manager = SessionManager()
streaming_card = FeishuStreamingCard(APP_ID, APP_SECRET)

# ========== 流式任务执行 ==========
def execute_streaming_task(chat_id: str, user_message: str, msg_id: str):
    """执行流式任务"""
    task_id = str(uuid.uuid4())[:8]
    log.info(f"开始流式任务 {task_id} for chat {chat_id}")

    try:
        # 创建流式卡片
        card_info = streaming_card.create_card()
        card_id = card_info["card_id"]
        sequence = card_info["sequence"]

        # 发送卡片
        streaming_card.send_card(chat_id, card_id, reply_to=msg_id)
        log.info(f"任务 {task_id} 创建卡片: {card_id}")

        # 获取会话历史
        session = session_manager.get_session(chat_id)
        messages = session.get_messages()
        messages.append({"role": "user", "content": user_message})

        # 调用 Anthropic API 流式接口
        accumulated_text = ""
        last_update_time = time.time()
        update_interval = 0.2  # 每200ms更新一次

        with anthropic_client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=messages,
            system="你是一个有帮助的AI助手。"
        ) as stream:
            for text in stream.text_stream:
                accumulated_text += text

                # 节流更新
                now = time.time()
                if now - last_update_time >= update_interval:
                    sequence = streaming_card.update_card(card_id, sequence, accumulated_text)
                    last_update_time = now

        # 最终更新
        final_text = stream.get_final_text()
        sequence = streaming_card.update_card(card_id, sequence, final_text)

        # 保存到历史
        session.add_message("user", user_message)
        session.add_message("assistant", final_text)

        log.info(f"任务 {task_id} 完成，输出长度: {len(final_text)}")

    except Exception as e:
        log.error(f"任务 {task_id} 执行失败: {e}", exc_info=True)
        try:
            error_msg = f"❌ 执行出错：{str(e)}"
            streaming_card.update_card(card_id, sequence, error_msg)
        except:
            pass

# ========== 消息处理 ==========
def is_allowed(open_id: str) -> bool:
    """检查用户是否有权限"""
    return open_id in ALLOWED_OPEN_IDS

def send_message(chat_id: str, text: str):
    """发送文本消息"""
    try:
        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(json.dumps({"text": text}))
                .build()
            ).build()
        feishu_client.im.v1.message.create(request)
    except Exception as e:
        log.error(f"发送消息失败: {e}")

def add_reaction(msg_id: str, emoji: str):
    """添加表情回应"""
    try:
        request = CreateMessageReactionRequest.builder() \
            .message_id(msg_id) \
            .request_body(
                CreateMessageReactionRequestBody.builder()
                .reaction_type(
                    Emoji.builder()
                    .emoji_type(emoji)
                    .build()
                ).build()
            ).build()
        feishu_client.im.v1.message_reaction.create(request)
    except Exception as e:
        log.error(f"添加表情失败: {e}")

def handle_message_event(data: dict):
    """处理消息事件"""
    try:
        event = data.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})

        sender_open_id = sender.get("sender_id", {}).get("open_id", "")
        msg_type = message.get("message_type", "")
        chat_id = message.get("chat_id", "")
        msg_id = message.get("message_id", "")
        content_str = message.get("content", "{}")

        log.info(f"收到消息 | sender={sender_open_id} | type={msg_type} | chat={chat_id}")

        # 权限校验
        if not is_allowed(sender_open_id):
            log.warning(f"拒绝未授权用户: {sender_open_id}")
            send_message(chat_id, "🚫 你没有权限使用此机器人")
            return

        # 只处理文本消息
        if msg_type != "text":
            send_message(chat_id, "⚠️ 目前只支持文本命令")
            return

        content = json.loads(content_str)
        text = content.get("text", "").strip()

        if not text:
            return

        # 处理特殊指令
        if text in ["/help", "帮助"]:
            help_text = """
🤖 飞书 Claude Bot（流式版本）
━━━━━━━━━━━━━━━━━━━━

✨ 支持实时流式输出，像打字机一样显示回复
💡 每个聊天都有独立的对话上下文
💾 对话历史自动保存

📋 命令：
  /help   - 显示帮助
  /reset  - 重置会话
"""
            send_message(chat_id, help_text)
            return

        if text in ["/reset", "重置"]:
            session_manager.close_session(chat_id)
            history_file = SESSIONS_DIR / f"{chat_id}.json"
            if history_file.exists():
                history_file.unlink()
            send_message(chat_id, "✅ 会话已重置")
            return

        # 添加思考表情
        add_reaction(msg_id, "THINKING")

        # 异步执行流式任务
        thread = threading.Thread(
            target=execute_streaming_task,
            args=(chat_id, text, msg_id),
            daemon=True
        )
        thread.start()

    except Exception as e:
        log.error(f"handle_message_event 异常: {e}", exc_info=True)

# ========== 主程序 ==========
def main():
    log.info("=" * 50)
    log.info("🚀 飞书 Claude Bot 启动（流式版本）")
    log.info(f"📁 工作目录: {WORK_DIR}")
    log.info(f"👥 授权用户数: {len(ALLOWED_OPEN_IDS)}")
    log.info("=" * 50)

    # 注册事件处理器
    handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(handle_message_event) \
        .build()

    # 启动 WebSocket 长连接
    cli = lark.ws.Client(APP_ID, APP_SECRET, event_handler=handler)
    cli.start()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("收到退出信号，正在关闭...")
        sys.exit(0)
