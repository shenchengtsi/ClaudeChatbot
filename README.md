# 飞书 Claude Code Bot

通过飞书消息远程控制 Mac Mini 上的 Claude Code。

## ✨ 特性

- 🤖 通过飞书消息远程执行 Claude Code
- 💬 每个聊天（私聊/群聊）独立的对话上下文
- 🔒 用户白名单权限控制
- 🔄 自动会话管理（30分钟无活动自动清理）
- 📝 支持思考表情已读状态
- 🚀 WebSocket 长连接（无需公网 IP）

## 📦 安装

### 1. 克隆仓库

```bash
git clone <your-repo-url>
cd feishu-claude-bot
```

### 2. 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置

复制配置模板：
```bash
cp config.example.py config.py
```

编辑 `config.py` 填写：
- `APP_ID` 和 `APP_SECRET`（从飞书开放平台获取）
- `ALLOWED_OPEN_IDS`（你的飞书 Open ID）
- `CLAUDE_PATH`（Claude Code 路径，运行 `which claude` 查看）

### 4. 飞书开放平台配置

1. 访问 https://open.feishu.cn/app
2. 创建企业自建应用，添加「机器人」能力
3. 权限管理中开启：
   - `im:message`
   - `im:message:send_as_bot`
   - `im:message.reaction:create`
   - `im:message.group_at_msg:readonly`（群聊需要）
4. 事件与回调 → 选择「使用长连接接收事件」
5. 添加事件：`im.message.receive_v1`
6. 发布应用

### 5. 获取 Open ID

```bash
./get_openid.sh
```

在飞书给机器人发消息，终端会显示你的 Open ID，复制到 `config.py` 中。

### 6. 启动 Bot

```bash
./start.sh
```

## 📖 使用方式

在飞书中直接给机器人发消息：

| 命令 | 说明 |
|------|------|
| `帮我写一个爬虫` | Claude Code 执行并返回结果 |
| `解释 ~/project/main.py` | 分析指定文件 |
| `/pwd` | 查看当前工作目录 |
| `/cd ~/project` | 切换工作目录 |
| `/status` | 查看 Bot 状态 |
| `/reset` | 重置当前会话 |
| `/help` | 显示帮助 |

## 🔄 版本管理

发布新版本：

```bash
python3 release.py "更新说明" [major|minor|patch]
```

示例：
```bash
# 补丁版本（默认）
python3 release.py "修复 bug"

# 小版本更新
python3 release.py "添加新功能" minor

# 大版本更新
python3 release.py "重大更新" major
```

发布后会自动：
- 递增版本号
- 提交代码到 Git
- 推送到 GitHub
- 通过飞书 Webhook 发送通知

## 🚀 开机自启（可选）

```bash
# 复制配置文件
cp com.feishu.claudebot.plist ~/Library/LaunchAgents/

# 加载服务
launchctl load ~/Library/LaunchAgents/com.feishu.claudebot.plist

# 查看状态
launchctl list | grep claudebot
```

## 📝 日志

```bash
# 实时查看日志
tail -f ~/feishu-claude-bot/bot.log

# 查看错误日志
tail -f ~/feishu-claude-bot/bot.error.log
```

## ⚠️ 注意事项

- Bot 可以执行任何 Claude Code 命令，请谨慎授权
- 建议只在私人飞书账号中使用
- 每个聊天有独立的 Claude Code 会话
- 会话会记住之前的对话内容
- 30分钟无活动会自动清理会话

## 📄 许可证

MIT License
