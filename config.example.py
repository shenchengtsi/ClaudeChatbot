# =====================================================
#   飞书 Claude Code Bot - 配置文件模板
#   复制此文件为 config.py 并填写你的配置
# =====================================================

# ===== 【必填】飞书应用凭证 =====
# 在飞书开放平台 https://open.feishu.cn 创建应用后获取
APP_ID = "cli_xxxxxxxxxxxxxxxxx"       # 替换为你的 App ID
APP_SECRET = "xxxxxxxxxxxxxxxxxxxxxx"  # 替换为你的 App Secret


# ===== 【强烈建议填写】授权用户白名单 =====
# 只有白名单内的飞书用户才能控制这台 Mac Mini
# 获取方式：运行 python3 get_my_openid.py 获取你的 Open ID
# 可填多个，例如：["ou_abc123", "ou_def456"]
ALLOWED_OPEN_IDS = [
    # "ou_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",  # 你的飞书 Open ID
]


# ===== 工作目录 =====
# Claude Code 执行命令时的默认目录
# 建议填写你的项目目录或主目录
import os
WORK_DIR = os.path.expanduser("~/Desktop")


# ===== Claude Code 路径 =====
# 如果 claude 命令不在 PATH 里，填写完整路径
# 通常是 /usr/local/bin/claude 或 ~/.npm-global/bin/claude
# 运行 `which claude` 查看
CLAUDE_PATH = "claude"


# ===== 执行超时（秒）=====
# Claude Code 单次执行最长时间，超时则自动中止
TIMEOUT = 180


# ===== 输出最大长度（字符数）=====
# 飞书单条消息有长度限制，超出会被截断
MAX_OUTPUT_LEN = 3000
