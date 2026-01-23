#!/usr/bin/env python3
"""
triage_core.py

可被脚本/服务端复用的 triage 核心逻辑（纯本地启发式）。

输入：单封邮件 dict（通常来自 out/emails/<id>.json）
输出：triage dict，并可选择写入 out/triage/<id>.triage.json
"""

from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------
# Heuristics (edit freely)
# ----------------------------

BUG_WORDS = [
    "bug",
    "crash",
    "freeze",
    "hang",
    "stuck",
    "not working",
    "doesn't work",
    "broken",
    "error",
    "exception",
    "traceback",
    "fail",
    "failed",
    "failure",
    "issue",
    "can't",
    "cannot",
    "unable",
    "won't",
    "does not",
    "wrong",
]

FEATURE_WORDS = [
    "feature",
    "request",
    "could you",
    "can you add",
    "please add",
    "wishlist",
    "support",
    "would be great",
    "enhancement",
    "improve",
    "improvement",
]

QUESTION_WORDS = [
    "how do i",
    "how to",
    "what is",
    "where is",
    "can i",
    "is it possible",
    "question",
    "help",
    "why",
]

ACCOUNT_WORDS = [
    "login",
    "log in",
    "sign in",
    "sign-in",
    "account",
    "subscription",
    "billing",
    "refund",
    "payment",
    "charge",
    "invoice",
    "receipt",
    "plan",
    "upgrade",
    "cancel",
]

P0_WORDS = [
    "data loss",
    "lost emails",
    "lost mail",
    "security",
    "breach",
    "leak",
    "cannot access",
    "locked out",
    "account hacked",
]

P1_WORDS = [
    "crash",
    "freeze",
    "hang",
    "stuck",
    "cannot send",
    "can't send",
    "cannot receive",
    "can't receive",
    "urgent",
    "immediately",
    "asap",
]

P2_WORDS = [
    "slow",
    "lag",
    "delay",
    "sometimes",
    "intermittent",
    "occasionally",
]

DEFAULT_PRIORITY = "P3"


# ----------------------------
# File/Path helpers
# ----------------------------


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, data: Dict[str, Any]) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def discover_input_files(input_glob: str) -> List[str]:
    files = glob.glob(input_glob)
    # newest first by mtime
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files


def email_path_for_id(email_id: str, emails_dir: str = "out/emails") -> str:
    return os.path.join(emails_dir, f"{email_id}.json")


def triage_path_for_id(email_id: str, triage_dir: str = "out/triage") -> str:
    return os.path.join(triage_dir, f"{email_id}.triage.json")


# ----------------------------
# Data extraction / normalization
# ----------------------------


def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    try:
        return str(x)
    except Exception:
        return ""


def normalize_text(*parts: str) -> str:
    txt = "\n".join([p for p in parts if p]).strip().lower()
    txt = re.sub(r"\s+", " ", txt)
    return txt


def extract_core_fields(email: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    """
    Best-effort extraction from different possible schemas.
    Returns: (email_id, thread_id, subject, from_email, date_str)
    """
    email_id = _safe_str(email.get("id") or email.get("email_id") or email.get("message_id"))
    thread_id = _safe_str(email.get("threadId") or email.get("thread_id"))
    subject = _safe_str(email.get("subject"))
    from_email = _safe_str(email.get("from") or email.get("from_email") or email.get("sender"))
    date_str = _safe_str(email.get("date") or email.get("internalDate") or email.get("received_at"))
    return email_id, thread_id, subject, from_email, date_str


def extract_body(email: Dict[str, Any]) -> Tuple[str, str]:
    snippet = _safe_str(email.get("snippet"))
    body_text = _safe_str(email.get("body_text") or email.get("body") or email.get("text"))
    return snippet, body_text


def extract_attachments(email: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Expect a list of dicts like:
      [{"filename": "...", "mimeType": "...", "saved_to": "...", "size": 1234}, ...]
    but tolerate other forms.
    """
    atts = email.get("attachments")
    if isinstance(atts, list):
        norm: List[Dict[str, Any]] = []
        for a in atts:
            if isinstance(a, dict):
                norm.append(
                    {
                        "filename": _safe_str(a.get("filename") or a.get("name")),
                        "mimeType": _safe_str(a.get("mimeType") or a.get("mime_type")),
                        "saved_to": _safe_str(
                            a.get("saved_to") or a.get("path") or a.get("filepath") or a.get("file_path")
                        ),
                        "size": a.get("size"),
                        "error": _safe_str(a.get("error")),
                    }
                )
            else:
                norm.append({"filename": _safe_str(a), "mimeType": "", "saved_to": "", "size": None, "error": ""})
        return norm
    return []


# ----------------------------
# Triage logic
# ----------------------------


def classify(text: str) -> str:
    t = text
    # Account/Billing first (prevents "issue" => bug)
    if any(w in t for w in ACCOUNT_WORDS):
        return "account_support"
    if any(w in t for w in BUG_WORDS):
        return "bug"
    if any(w in t for w in FEATURE_WORDS):
        return "feature_request"
    if any(w in t for w in QUESTION_WORDS):
        return "question"
    return "other"


def priority(text: str) -> str:
    t = text
    if any(w in t for w in P0_WORDS):
        return "P0"
    if any(w in t for w in P1_WORDS):
        return "P1"
    if any(w in t for w in P2_WORDS):
        return "P2"
    return DEFAULT_PRIORITY


def pick_summary(classification: str, subject: str) -> str:
    subj = subject.strip() if subject else "(no subject)"
    prefix = {
        "bug": "[BUG]",
        "feature_request": "[FEAT]",
        "question": "[Q]",
        "account_support": "[ACCOUNT]",
        "other": "[OTHER]",
    }.get(classification, "[OTHER]")
    return f"{prefix} {subj}"


def build_description(from_email: str, date_str: str, subject: str, snippet: str, body_text: str) -> str:
    # Keep it readable for Jira (and safe for later AI steps)
    body_preview = body_text.strip()
    if len(body_preview) > 4000:
        body_preview = body_preview[:4000] + "\n\n...[truncated]..."

    parts = [
        f"From: {from_email}" if from_email else "From: (unknown)",
        f"Date: {date_str}" if date_str else f"Date: {datetime.utcnow().isoformat()}Z",
        f"Subject: {subject}" if subject else "Subject: (no subject)",
        "",
        "Snippet:",
        snippet or "(none)",
        "",
        "Body:",
        body_preview or "(none)",
    ]
    return "\n".join(parts)


def triage_one(email: Dict[str, Any]) -> Dict[str, Any]:
    email_id, thread_id, subject, from_email, date_str = extract_core_fields(email)
    snippet, body_text = extract_body(email)
    attachments = extract_attachments(email)

    text = normalize_text(subject, snippet, body_text)

    c = classify(text)
    p = priority(text)

    summary = pick_summary(c, subject)
    desc = build_description(from_email, date_str, subject, snippet, body_text)

    labels = ["feedback-triage", c, p]

    return {
        "email_id": email_id,
        "threadId": thread_id,
        "classification": c,
        "priority": p,
        "jira": {
            "summary": summary,
            "description": desc,
            "labels": labels,
            # extra structured fields (useful when you later call Jira API)
            "reporter_email": from_email,
            "subject": subject,
            "received_at": date_str,
            "snippet": snippet,
        },
        # passthrough attachments so later steps can reference local files
        "attachments": attachments,
    }


def triage_email_id(
    email_id: str,
    emails_dir: str = "out/emails",
    triage_dir: str = "out/triage",
) -> Dict[str, Any]:
    email_path = email_path_for_id(email_id, emails_dir=emails_dir)
    email = load_json(email_path)
    triaged = triage_one(email)
    out_path = triage_path_for_id(email_id, triage_dir=triage_dir)
    dump_json(out_path, triaged)
    return triaged


def load_triage_for_id(email_id: str, triage_dir: str = "out/triage") -> Optional[Dict[str, Any]]:
    path = triage_path_for_id(email_id, triage_dir=triage_dir)
    if not os.path.exists(path):
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def upsert_triage_fields(
    email_id: str,
    classification: str,
    priority_value: str,
    jira_summary: str,
    jira_description: str,
    jira_labels: List[str],
    triage_dir: str = "out/triage",
) -> Dict[str, Any]:
    """
    保持 triage schema 至少包含：
      classification, priority, jira{summary,description,labels}
    其他字段尽量保留（如果已有文件）。
    """
    path = triage_path_for_id(email_id, triage_dir=triage_dir)
    existing: Dict[str, Any] = {}
    if os.path.exists(path):
        try:
            existing = load_json(path)
        except Exception:
            existing = {}

    existing["email_id"] = existing.get("email_id") or email_id
    existing["classification"] = classification
    existing["priority"] = priority_value
    jira = existing.get("jira")
    if not isinstance(jira, dict):
        jira = {}
    jira["summary"] = jira_summary
    jira["description"] = jira_description
    jira["labels"] = jira_labels
    existing["jira"] = jira

    dump_json(path, existing)
    return existing

