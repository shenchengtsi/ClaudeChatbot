# 版本管理使用说明

## 日常开发流程

### 1. 修改代码
正常修改 `bot.py`、`config.py` 等文件

### 2. 发布新版本

```bash
cd ~/feishu-claude-bot
python3 release.py "更新说明" [版本类型]
```

**版本类型：**
- `patch`（默认）：小修复，如 1.0.0 → 1.0.1
- `minor`：新功能，如 1.0.0 → 1.1.0
- `major`：重大更新，如 1.0.0 → 2.0.0

**示例：**
```bash
# 修复 bug
python3 release.py "修复会话超时问题"

# 添加新功能
python3 release.py "添加多语言支持" minor

# 重大更新
python3 release.py "重构架构" major
```

### 3. 自动完成的操作

脚本会自动：
1. ✅ 递增版本号
2. ✅ 提交所有更改到 Git
3. ✅ 创建版本标签
4. ✅ 推送到 GitHub
5. ✅ 发送飞书通知

## 版本回滚

如果需要回滚到之前的版本：

```bash
# 查看所有版本
git tag

# 回滚到指定版本
git checkout v1.0.0

# 或者创建新分支
git checkout -b rollback-v1.0.0 v1.0.0
```

## 查看版本历史

```bash
# 查看所有提交
git log --oneline

# 查看所有标签
git tag -l

# 查看特定版本的详情
git show v1.0.0
```

## 当前版本

查看当前版本：
```bash
cat VERSION
```

## 注意事项

- ⚠️ `config.py` 已在 `.gitignore` 中，不会被提交（保护敏感信息）
- ⚠️ 日志文件和虚拟环境也不会被提交
- ✅ 每次发布都会自动通知到飞书
- ✅ GitHub 仓库：https://github.com/shenchengtsi/ClaudeChatbot
