from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass
class JiraConfig:
    base_url: str
    email: str
    api_token: str
    project_key: str
    issue_type_bug: str
    issue_type_task: str


class JiraError(RuntimeError):
    pass


def jira_config_from_dict(d: Dict[str, Any]) -> JiraConfig:
    base_url = str(d.get("base_url") or "").strip().rstrip("/")
    email = str(d.get("email") or "").strip()
    api_token = str(d.get("api_token") or "").strip()
    project_key = str(d.get("project_key") or "").strip()
    issue_type_bug = str(d.get("issue_type_bug") or "").strip() or "Bug"
    issue_type_task = str(d.get("issue_type_task") or "").strip() or "Task"

    missing = [k for k, v in {
        "base_url": base_url,
        "email": email,
        "api_token": api_token,
        "project_key": project_key,
    }.items() if not v]
    if missing:
        raise JiraError(f"Missing Jira settings: {', '.join(missing)}")

    return JiraConfig(
        base_url=base_url,
        email=email,
        api_token=api_token,
        project_key=project_key,
        issue_type_bug=issue_type_bug,
        issue_type_task=issue_type_task,
    )


def load_jira_config_from_env() -> JiraConfig:
    """
    从环境变量读取 Jira 配置。不要把 token 写进代码或提交到 git。
    """
    base_url = (os.getenv("JIRA_BASE_URL") or "").strip()
    email = (os.getenv("JIRA_EMAIL") or "").strip()
    api_token = (os.getenv("JIRA_API_TOKEN") or "").strip()
    project_key = (os.getenv("JIRA_PROJECT_KEY") or "").strip()
    issue_type_bug = (os.getenv("JIRA_ISSUE_TYPE_BUG") or "").strip() or "Bug"
    issue_type_task = (os.getenv("JIRA_ISSUE_TYPE_TASK") or "").strip() or "Task"

    missing = [k for k, v in {
        "JIRA_BASE_URL": base_url,
        "JIRA_EMAIL": email,
        "JIRA_API_TOKEN": api_token,
        "JIRA_PROJECT_KEY": project_key,
    }.items() if not v]
    if missing:
        raise JiraError(f"Missing Jira env vars: {', '.join(missing)}")

    return JiraConfig(
        base_url=base_url.rstrip("/"),
        email=email,
        api_token=api_token,
        project_key=project_key,
        issue_type_bug=issue_type_bug,
        issue_type_task=issue_type_task,
    )


def _basic_auth_header(email: str, api_token: str) -> str:
    raw = f"{email}:{api_token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("utf-8")


def issue_type_for_classification(cfg: JiraConfig, classification: str) -> str:
    c = (classification or "").strip()
    if c == "bug":
        return cfg.issue_type_bug
    # feature_request / account_support / question / other -> task（可按需细分）
    return cfg.issue_type_task


def create_issue_v2(
    cfg: JiraConfig,
    *,
    summary: str,
    description: str,
    labels: List[str],
    issue_type_name: str,
) -> Dict[str, Any]:
    """
    使用 Jira REST API v2（description 支持纯文本字符串，最省事）。
    返回包含 key/self 等字段的 JSON。
    """
    url = f"{cfg.base_url}/rest/api/2/issue"
    headers = {
        "Authorization": _basic_auth_header(cfg.email, cfg.api_token),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "fields": {
            "project": {"key": cfg.project_key},
            "issuetype": {"name": issue_type_name},
            "summary": summary or "(no summary)",
            "description": description or "",
            "labels": labels or [],
        }
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code >= 400:
        # 不要回显 token；只返回状态码和响应文本（可能包含错误原因）
        raise JiraError(f"Jira create issue failed ({resp.status_code}): {resp.text}")
    return resp.json()


def issue_browse_url(cfg: JiraConfig, issue_key: str) -> str:
    return f"{cfg.base_url}/browse/{issue_key}"

