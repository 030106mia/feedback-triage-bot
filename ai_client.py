from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests


class AiError(RuntimeError):
    pass


@dataclass
class AiConfig:
    provider: str  # openai_compatible / custom (future)
    base_url: str
    api_key: str
    model: str
    prompt: str


def _redact_secrets(text: str) -> str:
    """
    最小化泄露风险：把常见的 API key 片段打码（例如 OpenAI sk-...）。
    """
    if not text:
        return ""
    # openai keys: sk-...
    text = re.sub(r"\bsk-[A-Za-z0-9]{8,}\b", "sk-***", text)
    # bearer token style
    text = re.sub(r"(Bearer\s+)[A-Za-z0-9\-_\.]{8,}", r"\1***", text, flags=re.IGNORECASE)
    return text


def ai_config_from_settings(settings: Dict[str, Any]) -> AiConfig:
    ai = settings.get("ai") if isinstance(settings.get("ai"), dict) else {}
    prompt = (settings.get("prompt") or "").strip()
    provider = (ai.get("provider") or "").strip() or "openai_compatible"
    base_url = (ai.get("base_url") or "").strip() or "https://api.openai.com/v1"
    api_key = (ai.get("api_key") or "").strip()
    model = (ai.get("model") or "").strip() or "gpt-4o-mini"

    missing = []
    if not api_key:
        missing.append("AI api_key")
    if not prompt:
        missing.append("prompt")
    if missing:
        raise AiError(f"Missing AI settings: {', '.join(missing)}")

    return AiConfig(provider=provider, base_url=base_url.rstrip("/"), api_key=api_key, model=model, prompt=prompt)


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    容错：如果模型输出含多余文字，尽量截取第一段 JSON 对象。
    """
    text = (text or "").strip()
    if not text:
        raise AiError("Empty AI response")
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)
    # fallback: find first {...}
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise AiError(f"AI response is not JSON: {text[:200]}")


def analyze_email_openai_compatible(cfg: AiConfig, email: Dict[str, Any]) -> Dict[str, Any]:
    """
    期望模型返回 JSON（字段不可缺失）：
      {
        "result": "待处理" | "无需处理",
        "confidence": "high" | "medium" | "low",
        "reason": "...",
        "signals": ["...", "..."]
      }
    """
    url = f"{cfg.base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}

    # 把邮件字段打包给 prompt（你提供的规则在 cfg.prompt 里）
    variables = {
        "subject": email.get("subject", ""),
        "from": email.get("from", ""),
        "date": email.get("date", ""),
        "snippet": email.get("snippet", ""),
        "body_text": email.get("body_text", ""),
    }
    user_content = cfg.prompt.strip() + "\n\n【输入邮件】\n" + json.dumps(variables, ensure_ascii=False)

    payload: Dict[str, Any] = {
        "model": cfg.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个严格的分类器。你必须只输出 JSON，对象字段必须包含："
                    "result, confidence, reason, signals。不要输出任何额外文本。"
                ),
            },
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code >= 400:
        raise AiError(f"AI request failed ({resp.status_code}): {_redact_secrets(resp.text)[:500]}")
    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        raise AiError(f"Unexpected AI response: {_redact_secrets(json.dumps(data, ensure_ascii=False))[:500]}")
    out = _extract_json_from_text(content)
    return out


def analyze_email(cfg: AiConfig, email: Dict[str, Any]) -> Dict[str, Any]:
    if cfg.provider == "openai_compatible":
        return analyze_email_openai_compatible(cfg, email)
    raise AiError(f"Unsupported provider: {cfg.provider}")


def generate_jira_draft_openai_compatible(
    cfg: AiConfig,
    *,
    email: Dict[str, Any],
    issue_type_name: str,
    ai_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    期望模型返回 JSON：
      {
        "summary": "...",
        "description": "...",
        "labels": ["a", "b"]
      }
    """
    url = f"{cfg.base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}

    variables = {
        "issue_type_name": issue_type_name,
        "subject": email.get("subject", ""),
        "from": email.get("from", ""),
        "date": email.get("date", ""),
        "body_text": email.get("body_text", ""),
        "ai": ai_context or {},
    }

    system = (
        "你是一个 Jira 工单撰写助手。你必须只输出 JSON（不要输出任何额外文本）。"
        "JSON 必须包含 summary, description, labels 三个字段。"
        "summary 简洁明确；description 用多行文本，包含问题/背景/复现(如有)/期望/建议处理；"
        "labels 为 0~6 个短标签（英文或拼音均可），不包含空格。"
        "不要包含任何 snippet 字段（输入里也没有）。"
    )
    user = "基于以下输入生成 Jira 工单草稿：\n" + json.dumps(variables, ensure_ascii=False)

    payload: Dict[str, Any] = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code >= 400:
        raise AiError(f"AI request failed ({resp.status_code}): {_redact_secrets(resp.text)[:500]}")
    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        raise AiError(f"Unexpected AI response: {_redact_secrets(json.dumps(data, ensure_ascii=False))[:500]}")
    out = _extract_json_from_text(content)

    summary = str(out.get("summary") or "").strip()
    description = str(out.get("description") or "").strip()
    labels = out.get("labels")
    if not isinstance(labels, list):
        labels = []
    labels2 = []
    for x in labels:
        s = str(x or "").strip()
        if not s:
            continue
        if s not in labels2:
            labels2.append(s)

    if not summary:
        summary = str(email.get("subject") or "").strip() or "(no subject)"

    return {"summary": summary, "description": description, "labels": labels2}


