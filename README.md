# feedback-triage-bot

一个用于拉取 Gmail 邮件到本地并生成 triage JSON 的小工具，并提供一个“零前端构建成本”的本地 Web UI 用于查看/运行/编辑 triage。

## Web UI（本地可交互页面）

### 安装与启动

在 repo 根目录执行：

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn web.server:app --reload --port 8000
```

浏览器打开：

- `http://localhost:8000`

### 页面说明（MVP）

- **`/`**：读取 `out/emails/*.json` 的邮件列表（按文件 mtime 新到旧）
- **`/email/{email_id}`**：邮件详情 + triage 结果
  - **Run Triage**：生成/覆盖写入 `out/triage/{email_id}.triage.json`（HTMX 局部刷新）
  - **Save**：编辑并保存 `classification / priority / jira.summary / jira.description / jira.labels`
- **`/work`**：快速处理队列（默认“候选”），一键“创建 Jira/跳过/已处理”，自动下一封，并在 `out/triage_state/` 记录状态
- **`/settings`**：本地配置页（Jira / AI API），保存到 `out/settings.json`
- **`/triage`**：批量 triage 最近 N 封（默认 5），显示进度与结果（允许失败不中断）
- **`/fetch`**：手动拉取 Gmail 指定标签下的收件（默认排除你发出的邮件），落盘到 `out/emails/`

## 数据来源

Web UI **优先读取本地落盘**的邮件数据：

- 邮件：`out/emails/<email_id>.json`
- triage：`out/triage/<email_id>.triage.json`

> 这意味着你不需要每次启动 Web 都去访问 Gmail API；只要 `out/emails` 已有数据即可。

## Gmail OAuth（可选）

如果你需要从 Gmail 拉取最新邮件，请先准备 `secrets/gmail_credentials.json`（保持在 `.gitignore` 中），然后运行：

```bash
python authorize_gmail.py
python fetch_full.py --label "Support收件"
```

## Jira 集成（可选）

> 推荐：直接打开 `http://localhost:8000/settings` 配置 Jira（会保存到本地 `out/settings.json`，已被 git 忽略）。
>
> 重要：**不要把 token 明文写进代码或提交到 git，也不要发到聊天里**。

你也可以用环境变量方式（作为 fallback）：

```bash
export JIRA_BASE_URL="https://xindong.atlassian.net"
export JIRA_EMAIL="liumeiyan@xd.com"
export JIRA_API_TOKEN="***"
export JIRA_PROJECT_KEY="FILO"
export JIRA_ISSUE_TYPE_BUG="缺陷"
export JIRA_ISSUE_TYPE_TASK="任务"
```

## 部署到 Vercel（可选）

已添加 Vercel Serverless 入口（`api/index.py` + `vercel.json`），可以直接部署。

### 重要限制（必须知道）

- Vercel Serverless **不适合写本地文件做持久化**：`out/triage/*.json`、`out/triage_state/*.json`、`out/settings.json` 在云端无法稳定持久保存。
- 因此在 Vercel 上默认开启 **只读模式**：可以浏览页面，但不允许 Run/Save/创建 Jira 等写操作。
- 如果你要在云端也能“保存 triage/状态/设置”，需要接入外部存储（例如 Vercel KV / Postgres / S3），再把写入改为写到外部存储。

### 部署步骤（概览）

- 把项目推到 GitHub
- 在 Vercel 导入该 repo
- 如需 Jira/AI：在 Vercel 项目 Settings → Environment Variables 配置对应变量（Jira：`JIRA_*`，AI：你后续定义的 `AI_*`）

然后打开 `http://localhost:8000/work?scope=candidate`，点击 **“创建 Jira（保存并下一封）”**：

- 会用 `triage` 里的 `jira.summary / jira.description / jira.labels` 创建 Jira issue（REST API v2）
- 成功后会在 `out/triage_state/<email_id>.state.json` 写入 `jira.key / jira.url` 并标记状态为 `jira`

