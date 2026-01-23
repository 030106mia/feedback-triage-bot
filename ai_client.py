from __future__ import annotations

import json
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
        raise AiError(f"AI request failed ({resp.status_code}): {resp.text[:500]}")
    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        raise AiError(f"Unexpected AI response: {json.dumps(data)[:500]}")
    out = _extract_json_from_text(content)
    return out


def analyze_email(cfg: AiConfig, email: Dict[str, Any]) -> Dict[str, Any]:
    if cfg.provider == "openai_compatible":
        return analyze_email_openai_compatible(cfg, email)
    raise AiError(f"Unsupported provider: {cfg.provider}")

