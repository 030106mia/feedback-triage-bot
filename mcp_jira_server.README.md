## Jira MCP（本地 stdio server）

这个仓库新增了一个最小可用的 Jira MCP Server：`mcp_jira_server.py`。

### 1) 配置（你说你会自己填）

推荐用环境变量（避免把 token 写进代码/提交到 git）：

```bash
export JIRA_BASE_URL="https://xxx.atlassian.net"
export JIRA_EMAIL="you@example.com"
export JIRA_API_TOKEN="***"
```

你也可以直接改 `mcp_jira_server.py` 顶部的 `JIRA_EMAIL/JIRA_API_TOKEN`（不推荐提交）。

### 2) 运行（stdio）

```bash
python mcp_jira_server.py
```

它会从 stdin 读 JSON-RPC 消息、从 stdout 输出 JSON-RPC 响应。

### 3) 暴露的 tools

- `jira.create_issue`：创建工单（v2）
- `jira.get_issue`：查询工单（v3）
- `jira.search`：JQL 搜索（v3/search）

### 4) 在 Cursor 里注册（示例）

不同版本 Cursor 配置入口不一样，这里给一个“命令式 MCP server”常见写法示例（你按自己环境改路径）：

```json
{
  "mcpServers": {
    "jira-mcp": {
      "command": "python",
      "args": ["mcp_jira_server.py"],
      "env": {
        "JIRA_BASE_URL": "https://xxx.atlassian.net",
        "JIRA_EMAIL": "you@example.com",
        "JIRA_API_TOKEN": "***"
      }
    }
  }
}
```

### 备注：为什么还可能用到 project_key？

`jira.get_issue` / `jira.search` 不需要 `project_key`。

但 **`jira.create_issue` 创建工单时 Jira 必须知道归属项目**，所以需要你在调用参数里传 `project_key`，或设置环境变量 `JIRA_PROJECT_KEY`。

