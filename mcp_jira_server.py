"""
Jira MCP Server (stdio)
======================

这是一个最小可用的 MCP（Model Context Protocol）server，实现 JSON-RPC over stdio，
提供 Jira 常用工具：创建工单 / 查询工单 / JQL 搜索。

你可以先把下面的常量改成你自己的（或改为从环境变量读取）。
注意：不要把 token 提交到 git。
"""

from __future__ import annotations

import base64
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


# ========= 你稍后会在这里填入/更新 =========
# 推荐做法：用环境变量（JIRA_*）注入；这里提供默认值占位。
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").strip().rstrip("/")
# project_key 对 get/search 并不需要；create_issue 时才会用到（可从参数或环境变量提供）
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "").strip()
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "").strip()
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "").strip()


class MCPError(Exception):
    def __init__(self, code: int, message: str, data: Any | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


@dataclass
class JiraCfg:
    base_url: str
    email: str
    api_token: str


def _basic_auth_header(email: str, api_token: str) -> str:
    raw = f"{email}:{api_token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("utf-8")


def _cfg_from_args(args: Dict[str, Any]) -> JiraCfg:
    base_url = str(args.get("base_url") or JIRA_BASE_URL or "").strip().rstrip("/")
    email = str(args.get("email") or JIRA_EMAIL or "").strip()
    api_token = str(args.get("api_token") or JIRA_API_TOKEN or "").strip()

    missing = [k for k, v in {
        "base_url": base_url,
        "email": email,
        "api_token": api_token,
    }.items() if not v]
    if missing:
        raise MCPError(
            code=-32000,
            message=f"Missing Jira config: {', '.join(missing)}. 请在环境变量 JIRA_* 或调用参数里提供。",
        )

    return JiraCfg(base_url=base_url, email=email, api_token=api_token)


def _jira_headers(cfg: JiraCfg) -> Dict[str, str]:
    return {
        "Authorization": _basic_auth_header(cfg.email, cfg.api_token),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def jira_create_issue(args: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _cfg_from_args(args)
    project_key = str(args.get("project_key") or JIRA_PROJECT_KEY or "").strip()
    if not project_key:
        raise MCPError(
            -32602,
            "create_issue 需要 project_key（可在调用参数里传 project_key，或设置环境变量 JIRA_PROJECT_KEY）",
        )
    summary = str(args.get("summary") or "").strip() or "(no summary)"
    description = str(args.get("description") or "")
    labels = args.get("labels") or []
    if isinstance(labels, str):
        labels = [s.strip() for s in labels.split(",") if s.strip()]
    if not isinstance(labels, list):
        raise MCPError(-32602, "labels 必须是 string 或 string[]")
    issue_type_name = str(args.get("issue_type_name") or "Task").strip() or "Task"

    url = f"{cfg.base_url}/rest/api/2/issue"
    payload: Dict[str, Any] = {
        "fields": {
            "project": {"key": project_key},
            "issuetype": {"name": issue_type_name},
            "summary": summary,
            "description": description,
            "labels": labels,
        }
    }

    resp = requests.post(url, headers=_jira_headers(cfg), json=payload, timeout=30)
    if resp.status_code >= 400:
        raise MCPError(-32001, f"Jira create issue failed ({resp.status_code})", data=_safe_text(resp))

    data = resp.json()
    key = data.get("key")
    if key:
        data["browse_url"] = f"{cfg.base_url}/browse/{key}"
    return data


def jira_get_issue(args: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _cfg_from_args(args)
    issue_key = str(args.get("issue_key") or "").strip()
    if not issue_key:
        raise MCPError(-32602, "issue_key 不能为空")

    fields = args.get("fields")
    qp = ""
    if fields:
        if isinstance(fields, str):
            qp = f"?fields={fields}"
        elif isinstance(fields, list):
            qp = "?fields=" + ",".join(str(x) for x in fields)
        else:
            raise MCPError(-32602, "fields 必须是 string 或 string[]")

    url = f"{cfg.base_url}/rest/api/3/issue/{issue_key}{qp}"
    resp = requests.get(url, headers=_jira_headers(cfg), timeout=30)
    if resp.status_code >= 400:
        raise MCPError(-32002, f"Jira get issue failed ({resp.status_code})", data=_safe_text(resp))
    return resp.json()


def jira_search(args: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _cfg_from_args(args)
    jql = str(args.get("jql") or "").strip()
    if not jql:
        raise MCPError(-32602, "jql 不能为空")

    max_results = args.get("max_results", 20)
    try:
        max_results_i = int(max_results)
    except Exception:
        raise MCPError(-32602, "max_results 必须是整数")

    fields = args.get("fields") or ["summary", "status", "issuetype", "created", "updated"]
    if isinstance(fields, str):
        fields = [s.strip() for s in fields.split(",") if s.strip()]
    if not isinstance(fields, list):
        raise MCPError(-32602, "fields 必须是 string 或 string[]")

    url = f"{cfg.base_url}/rest/api/3/search"
    payload = {"jql": jql, "maxResults": max_results_i, "fields": fields}
    resp = requests.post(url, headers=_jira_headers(cfg), json=payload, timeout=30)
    if resp.status_code >= 400:
        raise MCPError(-32003, f"Jira search failed ({resp.status_code})", data=_safe_text(resp))
    return resp.json()


def _safe_text(resp: requests.Response) -> str:
    try:
        # Jira 可能返回 HTML/JSON，这里尽量转成可读字符串；不回显任何 auth 信息
        return resp.text[:5000]
    except Exception:
        return "<no response text>"


# ========= MCP JSON-RPC plumbing =========

def _send(obj: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _result(id_: Any, result: Any) -> None:
    _send({"jsonrpc": "2.0", "id": id_, "result": result})


def _error(id_: Any, code: int, message: str, data: Any | None = None) -> None:
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    _send({"jsonrpc": "2.0", "id": id_, "error": err})


def _tools_list() -> Dict[str, Any]:
    # 结构按 MCP 的 tools/list 习惯返回（Cursor/Claude 生态都能识别）
    return {
        "tools": [
            {
                "name": "jira.create_issue",
                "description": "在 Jira 创建工单（REST API v2）。返回 key/self/browse_url。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string", "description": "Jira base url，如 https://xxx.atlassian.net（可选）"},
                        "project_key": {"type": "string", "description": "项目 key，如 FILO（create_issue 时需要；可选）"},
                        "email": {"type": "string", "description": "Jira 邮箱（可选）"},
                        "api_token": {"type": "string", "description": "Jira API token（可选）"},
                        "issue_type_name": {"type": "string", "description": "Issue type name，如 Task/缺陷/任务"},
                        "summary": {"type": "string"},
                        "description": {"type": "string"},
                        "labels": {"type": ["array", "string"], "items": {"type": "string"}},
                    },
                    "required": ["issue_type_name", "summary"],
                },
            },
            {
                "name": "jira.get_issue",
                "description": "按 issue key 查询工单（REST API v3）。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string"},
                        "email": {"type": "string"},
                        "api_token": {"type": "string"},
                        "issue_key": {"type": "string"},
                        "fields": {"type": ["array", "string"], "items": {"type": "string"}},
                    },
                    "required": ["issue_key"],
                },
            },
            {
                "name": "jira.search",
                "description": "用 JQL 搜索 issue（REST API v3/search）。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string"},
                        "email": {"type": "string"},
                        "api_token": {"type": "string"},
                        "jql": {"type": "string"},
                        "max_results": {"type": "integer", "default": 20},
                        "fields": {"type": ["array", "string"], "items": {"type": "string"}},
                    },
                    "required": ["jql"],
                },
            },
        ]
    }


def _dispatch_tool(name: str, arguments: Dict[str, Any]) -> Any:
    if name == "jira.create_issue":
        return jira_create_issue(arguments)
    if name == "jira.get_issue":
        return jira_get_issue(arguments)
    if name == "jira.search":
        return jira_search(arguments)
    raise MCPError(-32601, f"Unknown tool: {name}")


def main() -> None:
    # MCP 初始化：接受 initialize，tools/list，tools/call 三类请求
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            _error(None, -32700, f"Parse error: {e}")
            continue

        id_ = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}

        try:
            if method == "initialize":
                _result(id_, {
                    "serverInfo": {"name": "jira-mcp", "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                })
            elif method == "tools/list":
                _result(id_, _tools_list())
            elif method == "tools/call":
                tool_name = str(params.get("name") or "")
                arguments = params.get("arguments") or {}
                if not isinstance(arguments, dict):
                    raise MCPError(-32602, "arguments 必须是 object")
                out = _dispatch_tool(tool_name, arguments)
                # MCP 结果习惯用 content 数组（文本/JSON），这里直接返回 JSON 一条
                _result(id_, {"content": [{"type": "json", "json": out}]})
            else:
                raise MCPError(-32601, f"Method not found: {method}")
        except MCPError as e:
            _error(id_, e.code, e.message, e.data)
        except Exception as e:
            _error(id_, -32099, f"Unhandled error: {e}")


if __name__ == "__main__":
    main()

