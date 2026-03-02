#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书 Claude Code Bot
通过飞书消息远程控制 Mac Mini 上的 Claude Code
使用非交互模式 (-p) 配合历史上下文实现会话持久化
"""

import json
import subprocess
import threading
import logging
import os
import signal
import sys
import time
import re
from datetime import datetime
from pathlib import Path

import lark_oapi as lark
from lark_oapi.api.im.v1 import *

# ========== 加载配置 ==========
from config import APP_ID, APP_SECRET, ALLOWED_OPEN_IDS, WORK_DIR, CLAUDE_PATH, MAX_OUTPUT_LEN, TIMEOUT

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

# ========== 会话持久化目录 ==========
SESSIONS_DIR = Path("sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

# ========== Session 管理 ==========
class ClaudeSession:
    """管理单个 Claude Code 会话（使用非交互模式 + 历史上下文）"""
    def __init__(self, chat_id: str, restore_history=None):
        self.chat_id = chat_id
        self.last_activity = time.time()
        self.lock = threading.Lock()
        self.history = restore_history if restore_history else []  # 对话历史
        log.info(f"为 chat_id={self.chat_id} 创建新 session，历史记录数: {len(self.history)}")

    def send_message(self, text: str) -> str:
        """发送消息到 Claude Code 并获取响应"""
        with self.lock:
            try:
                self.last_activity = time.time()

                # 构建包含历史上下文的提示
                prompt = self._build_prompt_with_context(text)

                log.info(f"发送消息到 Claude (含 {len(self.history)} 条历史): {text[:50]}")

                # 使用非交互模式执行（跳过权限检查）
                result = subprocess.run(
                    [CLAUDE_PATH, '-p', '--dangerously-skip-permissions'],
                    input=prompt,
                    capture_output=True,
                    text=True,
                    cwd=WORK_DIR,
                    env={**os.environ, "CLAUDECODE": ""},
                    timeout=TIMEOUT
                )

                output = result.stdout.strip()

                if result.returncode != 0:
                    error_msg = result.stderr.strip()
                    log.error(f"Claude Code 执行失败 (返回码 {result.returncode}): {error_msg}")
                    return f"❌ 执行出错：{error_msg}"

                log.info(f"收到响应，长度: {len(output)} 字符")

                # 限制输出长度
                if len(output) > MAX_OUTPUT_LEN:
                    output = output[:MAX_OUTPUT_LEN] + f"\n\n⚠️ 输出过长，已截断（共{len(output)}字符）"

                result_text = output if output else "（命令执行完成，无输出）"

                # 保存到历史记录
                self.history.append({
                    "timestamp": datetime.now().isoformat(),
                    "user": text,
                    "assistant": result_text
                })

                # 持久化历史记录
                self._save_history()

                return result_text

            except subprocess.TimeoutExpired:
                log.error(f"执行超时（{TIMEOUT}秒）")
                return f"⏱️ 执行超时（超过{TIMEOUT}秒）"
            except Exception as e:
                log.error(f"发送消息失败: {e}", exc_info=True)
                return f"❌ 执行出错：{str(e)}"

    def _build_prompt_with_context(self, current_message: str) -> str:
        """构建包含历史上下文的提示"""
        if not self.history:
            # 没有历史记录，直接返回当前消息
            return current_message

        # 构建上下文（最近的 N 条对话）
        max_history = 5  # 保留最近5轮对话作为上下文
        recent_history = self.history[-max_history:]

        context_parts = ["以下是我们之前的对话历史：\n"]
        for i, entry in enumerate(recent_history, 1):
            context_parts.append(f"[{i}] 用户: {entry['user']}")
            context_parts.append(f"[{i}] 助手: {entry['assistant'][:200]}...")  # 截断长响应
            context_parts.append("")

        context_parts.append(f"现在，请回答我的新问题：{current_message}")

        return "\n".join(context_parts)

    def _save_history(self):
        """保存对话历史到文件"""
        try:
            history_file = SESSIONS_DIR / f"{self.chat_id}.json"
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "chat_id": self.chat_id,
                    "last_activity": self.last_activity,
                    "history": self.history
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error(f"保存历史失败: {e}")

    @staticmethod
    def load_history(chat_id: str):
        """从文件加载对话历史"""
        try:
            history_file = SESSIONS_DIR / f"{chat_id}.json"
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    log.info(f"为 chat_id={chat_id} 加载了 {len(data['history'])} 条历史记录")
                    return data['history']
        except Exception as e:
            log.error(f"加载历史失败: {e}")
        return None

    def get_history_summary(self) -> str:
        """获取历史记录摘要"""
        if not self.history:
            return "暂无对话历史"

        total = len(self.history)
        first_time = self.history[0]['timestamp']
        last_time = self.history[-1]['timestamp']

        return f"📊 对话历史统计\n" \
               f"━━━━━━━━━━━━━━━\n" \
               f"💬 总对话数：{total}\n" \
               f"🕐 首次对话：{first_time}\n" \
               f"🕐 最近对话：{last_time}\n" \
               f"📁 存储位置：sessions/{self.chat_id}.json"


class SessionManager:
    """管理所有聊天的 Claude Code 会话"""
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()

    def get_session(self, chat_id: str) -> ClaudeSession:
        """获取或创建会话"""
        with self.lock:
            if chat_id not in self.sessions:
                # 尝试加载历史记录
                history = ClaudeSession.load_history(chat_id)
                self.sessions[chat_id] = ClaudeSession(chat_id, restore_history=history)
            return self.sessions[chat_id]

    def close_session(self, chat_id: str):
        """关闭指定会话"""
        with self.lock:
            if chat_id in self.sessions:
                del self.sessions[chat_id]

# 全局 session 管理器
session_manager = SessionManager()


# ========== 工具函数 ==========

def send_message(chat_id: str, text: str):
    """发送文本消息到飞书"""
    try:
        request = CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(json.dumps({"text": text}, ensure_ascii=False))
                .build()
            ).build()
        resp = feishu_client.im.v1.message.create(request)
        if not resp.success():
            log.error(f"发送消息失败: {resp.msg}")
    except Exception as e:
        log.error(f"send_message 异常: {e}")


def reply_message(msg_id: str, text: str):
    """回复消息（引用原消息）"""
    try:
        request = ReplyMessageRequest.builder() \
            .message_id(msg_id) \
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type("text")
                .content(json.dumps({"text": text}, ensure_ascii=False))
                .build()
            ).build()
        resp = feishu_client.im.v1.message.reply(request)
        if not resp.success():
            log.error(f"回复消息失败: {resp.msg}")
    except Exception as e:
        log.error(f"reply_message 异常: {e}")


def add_reaction(msg_id: str, emoji_type: str = "FOLDED_HANDS"):
    """给消息添加表情回应"""
    try:
        from lark_oapi.api.im.v1 import CreateMessageReactionRequest, CreateMessageReactionRequestBody, Emoji
        request = CreateMessageReactionRequest.builder() \
            .message_id(msg_id) \
            .request_body(
                CreateMessageReactionRequestBody.builder()
                .reaction_type(Emoji.builder().emoji_type(emoji_type).build())
                .build()
            ).build()
        resp = feishu_client.im.v1.message_reaction.create(request)
        if not resp.success():
            log.error(f"添加表情失败: {resp.msg}")
    except Exception as e:
        log.error(f"add_reaction 异常: {e}")


def is_allowed(open_id: str) -> bool:
    """检查用户是否有权限"""
    if not ALLOWED_OPEN_IDS:
        # 未配置白名单则允许所有人（不推荐）
        log.warning("⚠️ 未配置 ALLOWED_OPEN_IDS，所有用户均可使用！")
        return True
    return open_id in ALLOWED_OPEN_IDS


def clean_text(text: str) -> str:
    """清理消息文本，移除@机器人的部分"""
    import re
    # 移除 @xxx 格式
    text = re.sub(r'@\S+', '', text).strip()
    return text


# ========== 消息处理 ==========

def handle_message_event(data):
    """处理飞书消息事件"""
    try:
        # 处理飞书事件对象
        if hasattr(data, 'event'):
            event = data.event
            message = event.message if hasattr(event, 'message') else {}
            sender = event.sender if hasattr(event, 'sender') else {}
        else:
            raw = data.to_dict() if hasattr(data, 'to_dict') else data
            event = raw.get("event", {})
            message = event.get("message", {})
            sender = event.get("sender", {})

        # 获取消息信息
        if hasattr(message, 'message_type'):
            # 对象模式
            sender_open_id = sender.sender_id.open_id if hasattr(sender, 'sender_id') else ""
            msg_type = message.message_type if hasattr(message, 'message_type') else ""
            chat_id = message.chat_id if hasattr(message, 'chat_id') else ""
            msg_id = message.message_id if hasattr(message, 'message_id') else ""
            content_str = message.content if hasattr(message, 'content') else "{}"
        else:
            # 字典模式
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
            send_message(chat_id, "⚠️ 目前只支持文本命令，请发送文字指令")
            return

        content = json.loads(content_str)
        text = content.get("text", "").strip()
        text = clean_text(text)

        if not text:
            return

        # 处理特殊指令
        if text in ["/help", "帮助", "help"]:
            send_message(chat_id, HELP_TEXT)
            return

        if text in ["/pwd", "当前目录"]:
            send_message(chat_id, f"📁 当前工作目录：\n{WORK_DIR}")
            return

        if text.startswith("/cd "):
            new_dir = text[4:].strip()
            handle_cd(chat_id, new_dir)
            return

        if text in ["/status", "状态"]:
            status_text = get_status()
            status_text += f"\n💬 活跃会话数：{len(session_manager.sessions)}"
            send_message(chat_id, status_text)
            return

        if text in ["/reset", "重置会话"]:
            session_manager.close_session(chat_id)
            # 删除历史文件
            history_file = SESSIONS_DIR / f"{chat_id}.json"
            if history_file.exists():
                history_file.unlink()
            send_message(chat_id, "✅ 会话已重置，对话历史已清空")
            return

        if text in ["/history", "历史", "查看历史"]:
            session = session_manager.get_session(chat_id)
            summary = session.get_history_summary()
            send_message(chat_id, summary)
            return

        # 添加思考表情表示已读
        add_reaction(msg_id, "THINKING")

        # 在新线程中执行，避免阻塞事件循环
        def execute():
            try:
                session = session_manager.get_session(chat_id)
                result = session.send_message(text)
                reply_message(msg_id, result)
            except Exception as e:
                log.error(f"执行失败: {e}", exc_info=True)
                reply_message(msg_id, f"❌ 执行出错：{str(e)}")

        t = threading.Thread(target=execute, daemon=True)
        t.start()

    except Exception as e:
        log.error(f"handle_message_event 异常: {e}", exc_info=True)


def handle_cd(chat_id: str, new_dir: str):
    """处理切换目录指令"""
    global WORK_DIR
    expanded = os.path.expanduser(new_dir)
    if os.path.isdir(expanded):
        WORK_DIR = expanded
        send_message(chat_id, f"✅ 已切换工作目录：\n{WORK_DIR}")
    else:
        send_message(chat_id, f"❌ 目录不存在：{expanded}")


def get_status() -> str:
    """获取当前状态信息"""
    return (
        f"📊 Bot 状态\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🟢 运行中\n"
        f"📁 工作目录：{WORK_DIR}\n"
        f"🤖 Claude 路径：{CLAUDE_PATH}\n"
        f"⏱ 超时设置：{TIMEOUT}s\n"
        f"🕐 当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


HELP_TEXT = """
🤖 飞书 Claude Code Bot 使用说明
━━━━━━━━━━━━━━━━━━━━
📌 直接发送任何指令，Claude Code 会在你的 Mac Mini 上执行
💡 每个聊天（私聊/群聊）都有独立的对话上下文
💾 对话历史会自动保存，Bot 重启后可恢复
🔄 使用历史上下文模拟会话持久化

📋 内置命令：
  /help      - 显示此帮助
  /pwd       - 查看当前工作目录
  /cd <路径> - 切换工作目录
  /status    - 查看 Bot 状态
  /history   - 查看对话历史统计
  /reset     - 重置当前会话（清除对话历史）

💡 示例指令：
  帮我写一个 Python 爬虫，保存到 ~/Desktop/crawler.py
  解释一下 ~/project/main.py 这个文件
  在当前目录创建一个 README.md
  列出 ~/Desktop 下所有 .py 文件

⚠️ 注意：
  - 所有操作都在 Mac Mini 本地执行
  - 每个聊天有独立的对话历史
  - 通过历史上下文保持对话连贯性
  - 对话历史保存在 sessions/ 目录
""".strip()


# ========== 主程序 ==========

def main():
    log.info("=" * 50)
    log.info("🚀 飞书 Claude Code Bot 启动")
    log.info(f"📁 工作目录: {WORK_DIR}")
    log.info(f"🤖 Claude 路径: {CLAUDE_PATH}")
    log.info(f"👥 授权用户数: {len(ALLOWED_OPEN_IDS)}")
    log.info("=" * 50)

    # 构建事件处理器
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(handle_message_event) \
        .build()

    # 使用 WebSocket 长连接（无需公网 IP）
    ws_client = lark.ws.Client(
        APP_ID,
        APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO
    )

    def shutdown(sig, frame):
        log.info("收到退出信号，正在关闭...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    ws_client.start()


if __name__ == "__main__":
    main()
