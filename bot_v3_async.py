#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书 Claude Code Bot - 异步版本
通过飞书消息远程控制 Mac Mini 上的 Claude Code
使用异步执行 + 轮询机制，避免长时间阻塞
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
import uuid
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

# ========== 异步任务管理 ==========
class AsyncTask:
    """异步任务"""
    def __init__(self, task_id: str, chat_id: str, msg_id: str, prompt: str):
        self.task_id = task_id
        self.chat_id = chat_id
        self.msg_id = msg_id
        self.prompt = prompt
        self.process = None
        self.start_time = time.time()
        self.result = None
        self.error = None
        self.completed = False
        self.cancelled = False

class AsyncTaskManager:
    """管理异步任务"""
    def __init__(self):
        self.tasks = {}
        self.lock = threading.Lock()

    def create_task(self, chat_id: str, msg_id: str, prompt: str) -> str:
        """创建新任务"""
        task_id = str(uuid.uuid4())[:8]
        task = AsyncTask(task_id, chat_id, msg_id, prompt)

        with self.lock:
            self.tasks[task_id] = task

        # 启动后台线程执行任务
        thread = threading.Thread(target=self._execute_task, args=(task,), daemon=True)
        thread.start()

        log.info(f"创建异步任务 {task_id} for chat {chat_id}")
        return task_id

    def _execute_task(self, task: AsyncTask):
        """在后台执行任务"""
        try:
            log.info(f"开始执行任务 {task.task_id}")

            # 执行 Claude Code
            # 创建环境变量副本，移除会导致嵌套检测的变量，但保留 API 凭证
            clean_env = {
                k: v for k, v in os.environ.items()
                if k not in ['CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_AGENT_SDK_VERSION']
            }

            # 确保包含 ANTHROPIC 凭证（从 settings.json 读取）
            if 'ANTHROPIC_BASE_URL' not in clean_env:
                clean_env['ANTHROPIC_BASE_URL'] = 'https://gaccode.com/claudecode'
            if 'ANTHROPIC_API_KEY' not in clean_env:
                clean_env['ANTHROPIC_API_KEY'] = 'sk-ant-oat01-621001787429909d196f476abaf986909a08c1b19bf7649df4acbef36b5e495c'

            # 使用 Popen 以便可以中途取消
            task.process = subprocess.Popen(
                [CLAUDE_PATH, '-p', '--dangerously-skip-permissions'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=WORK_DIR,
                env=clean_env
            )

            # 发送输入并等待完成，同时检查是否被取消
            try:
                stdout, stderr = task.process.communicate(input=task.prompt, timeout=TIMEOUT)

                # 检查是否被取消
                if task.cancelled:
                    task.error = "🛑 任务已被用户取消"
                    log.info(f"任务 {task.task_id} 被用户取消")
                    return

                output = stdout.strip()
                stderr = stderr.strip()

                log.info(f"任务 {task.task_id} 返回码: {task.process.returncode}, stdout长度: {len(output)}, stderr长度: {len(stderr)}")
                if stderr:
                    log.info(f"任务 {task.task_id} stderr: {stderr[:500]}")

                if task.process.returncode != 0:
                    error_msg = stderr
                    task.error = f"❌ 执行出错：{error_msg}"
                    log.error(f"任务 {task.task_id} 执行失败: {error_msg}")
                else:
                    # 限制输出长度
                    if len(output) > MAX_OUTPUT_LEN:
                        output = output[:MAX_OUTPUT_LEN] + f"\n\n⚠️ 输出过长，已截断（共{len(output)}字符）"

                    task.result = output if output else "（命令执行完成，无输出）"
                    log.info(f"任务 {task.task_id} 完成，输出长度: {len(output)} 字符")

            except subprocess.TimeoutExpired:
                task.process.kill()
                task.error = f"⏱️ 执行超时（超过{TIMEOUT}秒）"
                log.error(f"任务 {task.task_id} 超时")

        except subprocess.TimeoutExpired:
            task.error = f"⏱️ 执行超时（超过{TIMEOUT}秒）"
            log.error(f"任务 {task.task_id} 超时")
        except Exception as e:
            task.error = f"❌ 执行出错：{str(e)}"
            log.error(f"任务 {task.task_id} 异常: {e}", exc_info=True)
        finally:
            task.completed = True
            elapsed = time.time() - task.start_time
            log.info(f"任务 {task.task_id} 结束，耗时 {elapsed:.1f}秒")

            # 任务完成后，发送结果到飞书
            self._send_result(task)

    def _send_result(self, task: AsyncTask):
        """发送任务结果到飞书"""
        try:
            result_text = task.error if task.error else task.result
            elapsed = time.time() - task.start_time

            # 添加执行时间信息
            footer = f"\n\n⏱ 执行耗时: {elapsed:.1f}秒"
            final_text = result_text + footer

            reply_message(task.msg_id, final_text)
            log.info(f"已发送任务 {task.task_id} 的结果")
        except Exception as e:
            log.error(f"发送任务结果失败: {e}", exc_info=True)

    def get_task(self, task_id: str) -> AsyncTask:
        """获取任务"""
        with self.lock:
            return self.tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """取消正在运行的任务"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return False

            if task.completed:
                return False

            # 标记为已取消
            task.cancelled = True

            # 如果进程正在运行，终止它
            if task.process and task.process.poll() is None:
                try:
                    task.process.terminate()
                    log.info(f"已终止任务 {task_id} 的进程")
                except Exception as e:
                    log.error(f"终止任务 {task_id} 失败: {e}")

            return True

    def get_running_tasks(self, chat_id: str = None):
        """获取正在运行的任务列表"""
        with self.lock:
            running = []
            for task_id, task in self.tasks.items():
                if not task.completed:
                    if chat_id is None or task.chat_id == chat_id:
                        elapsed = time.time() - task.start_time
                        # 检查进程状态
                        is_alive = task.process and task.process.poll() is None
                        status = "运行中" if is_alive else "等待中"

                        running.append({
                            'task_id': task_id,
                            'chat_id': task.chat_id,
                            'prompt': task.prompt[:50] + '...' if len(task.prompt) > 50 else task.prompt,
                            'elapsed': elapsed,
                            'status': status
                        })
            return running

    def cleanup_old_tasks(self, max_age_seconds=3600):
        """清理旧任务（1小时以上）"""
        with self.lock:
            now = time.time()
            old_tasks = [
                tid for tid, task in self.tasks.items()
                if task.completed and (now - task.start_time) > max_age_seconds
            ]
            for tid in old_tasks:
                del self.tasks[tid]
            if old_tasks:
                log.info(f"清理了 {len(old_tasks)} 个旧任务")

# 全局任务管理器
task_manager = AsyncTaskManager()

# ========== Session 管理 ==========
class ClaudeSession:
    """管理单个 Claude Code 会话（使用非交互模式 + 历史上下文）"""
    def __init__(self, chat_id: str, restore_history=None):
        self.chat_id = chat_id
        self.last_activity = time.time()
        self.lock = threading.Lock()
        self.history = restore_history if restore_history else []  # 对话历史
        log.info(f"为 chat_id={self.chat_id} 创建新 session，历史记录数: {len(self.history)}")

    def send_message_async(self, text: str, msg_id: str) -> str:
        """异步发送消息到 Claude Code"""
        with self.lock:
            self.last_activity = time.time()

            # 构建包含历史上下文的提示
            prompt = self._build_prompt_with_context(text)

            log.info(f"异步发送消息到 Claude (含 {len(self.history)} 条历史): {text[:50]}")

            # 创建异步任务
            task_id = task_manager.create_task(self.chat_id, msg_id, prompt)

            # 先保存用户消息到历史（结果会在任务完成后更新）
            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "user": text,
                "assistant": f"[任务 {task_id} 处理中...]",
                "task_id": task_id
            })

            return task_id

    def update_history_with_result(self, task_id: str, result: str):
        """用任务结果更新历史记录"""
        with self.lock:
            # 找到对应的历史记录并更新
            for entry in reversed(self.history):
                if entry.get("task_id") == task_id:
                    entry["assistant"] = result
                    entry.pop("task_id", None)  # 移除 task_id 标记
                    self._save_history()
                    log.info(f"已更新任务 {task_id} 的历史记录")
                    break

    def _build_prompt_with_context(self, current_message: str) -> str:
        """构建包含历史上下文的提示"""
        if not self.history:
            return current_message

        # 构建上下文（最近的 N 条对话，排除处理中的任务）
        max_history = 10  # 增加到10条历史记录
        valid_history = [
            entry for entry in self.history
            if not entry.get("task_id")  # 排除处理中的任务
        ]
        recent_history = valid_history[-max_history:]

        if not recent_history:
            return current_message

        context_parts = ["以下是我们之前的对话历史：\n"]
        for i, entry in enumerate(recent_history, 1):
            user_msg = entry['user']
            assistant_msg = entry['assistant']

            # 限制单条消息长度，但保留更多信息（2000字符而不是200）
            max_msg_len = 2000
            if len(assistant_msg) > max_msg_len:
                assistant_msg = assistant_msg[:max_msg_len] + "...(内容过长已截断)"

            context_parts.append(f"[{i}] 用户: {user_msg}")
            context_parts.append(f"[{i}] 助手: {assistant_msg}")
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
        log.warning("⚠️ 未配置 ALLOWED_OPEN_IDS，所有用户均可使用！")
        return True
    return open_id in ALLOWED_OPEN_IDS


def clean_text(text: str) -> str:
    """清理消息文本，移除@机器人的部分"""
    import re
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
            sender_open_id = sender.sender_id.open_id if hasattr(sender, 'sender_id') else ""
            msg_type = message.message_type if hasattr(message, 'message_type') else ""
            chat_id = message.chat_id if hasattr(message, 'chat_id') else ""
            msg_id = message.message_id if hasattr(message, 'message_id') else ""
            content_str = message.content if hasattr(message, 'content') else "{}"
        else:
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
            status_text += f"\n⚙️ 运行中任务：{sum(1 for t in task_manager.tasks.values() if not t.completed)}"
            send_message(chat_id, status_text)
            return

        if text in ["/reset", "重置会话"]:
            session_manager.close_session(chat_id)
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

        if text.startswith("/cancel "):
            task_id = text[8:].strip()
            if task_manager.cancel_task(task_id):
                send_message(chat_id, f"✅ 已取消任务 {task_id}")
            else:
                send_message(chat_id, f"❌ 无法取消任务 {task_id}（任务不存在或已完成）")
            return

        if text in ["/tasks", "任务列表"]:
            running_tasks = task_manager.get_running_tasks(chat_id)
            if not running_tasks:
                send_message(chat_id, "📋 当前没有正在运行的任务")
            else:
                task_list = "📋 正在运行的任务：\n━━━━━━━━━━━━━━━\n"
                for t in running_tasks:
                    task_list += f"\n🔹 任务ID: {t['task_id']}\n"
                    task_list += f"   状态: {t['status']}\n"
                    task_list += f"   指令: {t['prompt']}\n"
                    if t['status'] == "运行中":
                        task_list += f"   已运行: {t['elapsed']:.1f}秒\n"
                    else:
                        task_list += f"   已等待: {t['elapsed']:.1f}秒\n"
                task_list += f"\n💡 使用 /cancel <任务ID> 取消任务"
                send_message(chat_id, task_list)
            return

        # 添加思考表情表示已读
        add_reaction(msg_id, "THINKING")

        # 异步执行任务
        session = session_manager.get_session(chat_id)
        task_id = session.send_message_async(text, msg_id)

        # 立即回复"正在处理中"
        reply_message(msg_id, f"⏳ 正在处理中...\n任务ID: {task_id}")

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
🤖 飞书 Claude Code Bot 使用说明（异步版本）
━━━━━━━━━━━━━━━━━━━━

📌 直接发送任何指令，Claude Code 会在你的 Mac Mini 上执行
💡 每个聊天（私聊/群聊）都有独立的对话上下文
💾 对话历史会自动保存，Bot 重启后可恢复
⚡ 使用异步执行，长任务不会阻塞其他请求

📋 内置命令：
  /help         - 显示此帮助
  /pwd          - 查看当前工作目录
  /cd <路径>    - 切换工作目录
  /status       - 查看 Bot 状态
  /history      - 查看对话历史统计
  /reset        - 重置当前会话（清除对话历史）
  /tasks        - 查看正在运行的任务
  /cancel <ID>  - 取消指定任务

💡 示例指令：
  帮我写一个 Python 爬虫，保存到 ~/Desktop/crawler.py
  解释一下 ~/project/main.py 这个文件
  在当前目录创建一个 README.md
  列出 ~/Desktop 下所有 .py 文件

⚠️ 注意：
  - 所有操作都在 Mac Mini 本地执行
  - 每个聊天有独立的对话历史
  - 长任务会异步执行，完成后自动回复
  - 对话历史保存在 sessions/ 目录
""".strip()


# ========== 主程序 ==========

def main():
    log.info("=" * 50)
    log.info("🚀 飞书 Claude Code Bot 启动（异步版本）")
    log.info(f"📁 工作目录: {WORK_DIR}")
    log.info(f"🤖 Claude 路径: {CLAUDE_PATH}")
    log.info(f"👥 授权用户数: {len(ALLOWED_OPEN_IDS)}")
    log.info(f"⏱ 超时设置: {TIMEOUT}秒")
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

    # 启动定期清理任务的线程
    def cleanup_loop():
        while True:
            time.sleep(3600)  # 每小时清理一次
            task_manager.cleanup_old_tasks()

    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()

    ws_client.start()


if __name__ == "__main__":
    main()
