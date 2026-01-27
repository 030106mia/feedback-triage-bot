from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional


DEFAULT_TRIAGE_STATE_DIR = "out/triage_state"


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def state_path(email_id: str, state_dir: str = DEFAULT_TRIAGE_STATE_DIR) -> str:
    return os.path.join(state_dir, f"{email_id}.state.json")


def load_state(email_id: str, state_dir: str = DEFAULT_TRIAGE_STATE_DIR) -> Optional[Dict[str, Any]]:
    path = state_path(email_id, state_dir=state_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return None
    except Exception:
        return None


def save_state(email_id: str, state: Dict[str, Any], state_dir: str = DEFAULT_TRIAGE_STATE_DIR) -> Dict[str, Any]:
    ensure_dir(state_dir)
    state = dict(state)
    state.setdefault("email_id", email_id)
    state["updated_at"] = _utc_now()
    path = state_path(email_id, state_dir=state_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return state


def set_status(
    email_id: str,
    status: str,
    *,
    state_dir: str = DEFAULT_TRIAGE_STATE_DIR,
    reason: str = "",
) -> Dict[str, Any]:
    """
    产品级状态（新）：
      - pending: 待处理
      - ignore: 无需处理
      - processed: 已处理

    兼容旧值：
      - todo -> pending
      - skip -> ignore
      - done/jira -> processed
    """
    existing = load_state(email_id, state_dir=state_dir) or {}
    status = (status or "").strip()
    if status in {"todo", "pending"}:
        existing["status"] = "pending"
    elif status in {"skip", "ignore"}:
        existing["status"] = "ignore"
    elif status in {"done", "jira", "processed"}:
        existing["status"] = "processed"
        existing.setdefault("processed_at", _utc_now())
    else:
        existing["status"] = "pending"
    if reason:
        existing["reason"] = reason
    return save_state(email_id, existing, state_dir=state_dir)


def mark_processed(email_id: str, *, state_dir: str = DEFAULT_TRIAGE_STATE_DIR) -> Dict[str, Any]:
    existing = load_state(email_id, state_dir=state_dir) or {}
    existing["status"] = "processed"
    existing["processed_at"] = _utc_now()
    return save_state(email_id, existing, state_dir=state_dir)


def mark_ignore(email_id: str, *, state_dir: str = DEFAULT_TRIAGE_STATE_DIR) -> Dict[str, Any]:
    existing = load_state(email_id, state_dir=state_dir) or {}
    existing["status"] = "ignore"
    return save_state(email_id, existing, state_dir=state_dir)


def set_jira_link(
    email_id: str,
    *,
    jira_key: str,
    jira_url: str,
    state_dir: str = DEFAULT_TRIAGE_STATE_DIR,
) -> Dict[str, Any]:
    existing = load_state(email_id, state_dir=state_dir) or {}
    existing["jira"] = {
        "key": jira_key,
        "url": jira_url,
        "created_at": _utc_now(),
    }
    # Jira 推进后视为已处理
    existing["status"] = "processed"
    existing.setdefault("processed_at", _utc_now())
    return save_state(email_id, existing, state_dir=state_dir)


def processing_status(state: Optional[Dict[str, Any]]) -> str:
    """
    统一对外展示的状态：
      - pending: 待处理
      - processed: 已处理
      - ignore: 无需处理

    兼容旧状态：
      todo -> pending
      done/jira -> processed
      skip -> ignore
    """
    if not state or not isinstance(state, dict):
        return "pending"
    s = str(state.get("status") or "").strip() or "pending"
    if s in {"pending", "processed", "ignore"}:
        return s
    if s == "todo":
        return "pending"
    if s in {"done", "jira"}:
        return "processed"
    if s == "skip":
        return "ignore"
    return "pending"


def upsert_ai_result(
    email_id: str,
    *,
    decision: str,
    reason: str = "",
    raw: Optional[Dict[str, Any]] = None,
    state_dir: str = DEFAULT_TRIAGE_STATE_DIR,
) -> Dict[str, Any]:
    """
    保存 AI 解析结果到状态层，并把 status 设置为 pending/ignore（不自动 processed）。
    """
    existing = load_state(email_id, state_dir=state_dir) or {}
    existing["ai"] = {
        "decision": decision,
        "reason": reason,
        "raw": raw or {},
        "parsed_at": _utc_now(),
    }
    # 不覆盖用户已处理结果
    cur = processing_status(existing)
    if cur == "processed":
        return save_state(email_id, existing, state_dir=state_dir)

    if decision == "ignore":
        existing["status"] = "ignore"
    else:
        existing["status"] = "pending"
    return save_state(email_id, existing, state_dir=state_dir)


def upsert_jira_draft(
    email_id: str,
    *,
    issue_type_name: str,
    summary: str,
    description: str,
    labels: list[str],
    state_dir: str = DEFAULT_TRIAGE_STATE_DIR,
) -> Dict[str, Any]:
    """
    保存 Jira 工单草稿（用于“生成工单”后可编辑再一键导入）。
    """
    existing = load_state(email_id, state_dir=state_dir) or {}
    existing["jira_draft"] = {
        "issue_type_name": issue_type_name,
        "summary": summary,
        "description": description,
        "labels": labels,
        "generated_at": _utc_now(),
    }
    return save_state(email_id, existing, state_dir=state_dir)

