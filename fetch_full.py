from __future__ import annotations

import argparse
import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_PATH = "secrets/gmail_token.json"

OUT_DIR = Path("out")
EMAILS_DIR = OUT_DIR / "emails"
ATTACH_DIR = OUT_DIR / "attachments"


def _safe_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    return name[:200] if len(name) > 200 else name


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def _get_header(headers: List[Dict[str, str]], key: str) -> str:
    key_lower = key.lower()
    for h in headers:
        if h.get("name", "").lower() == key_lower:
            return h.get("value", "")
    return ""


def _extract_text_from_payload(payload: Dict[str, Any]) -> str:
    """
    Prefer text/plain; fallback to text/html (strip tags lightly).
    Gmail message payload is a MIME tree: payload + parts[] nested.
    """
    texts_plain: List[str] = []
    texts_html: List[str] = []

    def walk(part: Dict[str, Any]) -> None:
        mime = part.get("mimeType", "")
        body = part.get("body", {}) or {}
        data = body.get("data")

        if mime == "text/plain" and data:
            try:
                texts_plain.append(_b64url_decode(data).decode("utf-8", errors="replace"))
            except Exception:
                pass
        elif mime == "text/html" and data:
            try:
                html = _b64url_decode(data).decode("utf-8", errors="replace")
                texts_html.append(html)
            except Exception:
                pass

        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)

    if texts_plain:
        return "\n\n".join(t.strip() for t in texts_plain if t.strip())

    if texts_html:
        # very light HTML strip; good enough for triage
        html = "\n\n".join(texts_html)
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
        text = re.sub(r"(?is)<br\s*/?>", "\n", text)
        text = re.sub(r"(?is)</p\s*>", "\n\n", text)
        text = re.sub(r"(?is)<.*?>", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    return ""


def _collect_attachments(
    service,
    user_id: str,
    msg_id: str,
    payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Download attachments to out/attachments/<msg_id>/<filename>
    Return metadata list.
    """
    attachments: List[Dict[str, Any]] = []

    def walk(part: Dict[str, Any]) -> None:
        filename = part.get("filename") or ""
        body = part.get("body", {}) or {}
        attachment_id = body.get("attachmentId")
        mime = part.get("mimeType", "")

        if attachment_id and filename:
            try:
                att = (
                    service.users()
                    .messages()
                    .attachments()
                    .get(userId=user_id, messageId=msg_id, id=attachment_id)
                    .execute()
                )
                data = att.get("data")
                if data:
                    content = _b64url_decode(data)
                    out_folder = ATTACH_DIR / msg_id
                    out_folder.mkdir(parents=True, exist_ok=True)
                    out_path = out_folder / _safe_filename(filename)
                    out_path.write_bytes(content)

                    attachments.append(
                        {
                            "filename": filename,
                            "mimeType": mime,
                            "size": len(content),
                            "saved_to": str(out_path),
                            "attachmentId": attachment_id,
                        }
                    )
            except Exception as e:
                attachments.append(
                    {
                        "filename": filename,
                        "mimeType": mime,
                        "error": str(e),
                        "attachmentId": attachment_id,
                    }
                )

        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    return attachments


def _list_message_ids(service, user_id: str, query: Optional[str], max_results: Optional[int]) -> List[str]:
    """
    分页列出 message ids。若 max_results 为 None，则拉取所有页。
    """
    ids: List[str] = []
    page_token: Optional[str] = None

    while True:
        page_size = 500
        if max_results is not None:
            remaining = max_results - len(ids)
            if remaining <= 0:
                break
            page_size = min(page_size, remaining)

        req = service.users().messages().list(
            userId=user_id,
            q=query or None,
            maxResults=page_size,
            pageToken=page_token or None,
        )
        resp = req.execute()
        msgs = resp.get("messages", []) or []
        ids.extend([m["id"] for m in msgs if isinstance(m, dict) and m.get("id")])

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    # 去重但保持顺序
    out: List[str] = []
    seen = set()
    for mid in ids:
        if mid not in seen:
            out.append(mid)
            seen.add(mid)
    return out


def _build_query(label: Optional[str], raw_query: Optional[str], exclude_from_me: bool) -> Optional[str]:
    parts: List[str] = []
    if raw_query:
        parts.append(raw_query.strip())
    if label:
        # label 名称可能包含空格/中文，建议用引号
        parts.append(f'label:"{label}"')
    if exclude_from_me:
        parts.append("-from:me")
        parts.append("-in:sent")
    q = " ".join([p for p in parts if p])
    return q or None


ProgressCallback = Callable[[int, int, str, str, Optional[str]], None]


def fetch_to_out(
    *,
    label: Optional[str] = None,
    query: Optional[str] = None,
    max_results: Optional[int] = None,
    include_from_me: bool = False,
    progress_cb: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """
    手动拉取入口（可被 Web/UI/脚本复用）。

    - label/query 会组合成 Gmail query
    - 默认排除你发出的邮件（-from:me -in:sent）
    - max_results=None 表示全量拉取

    progress_cb(done, total, msg_id, subject, error) 可用于展示进度。
    """
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(f"Missing {TOKEN_PATH}. Run authorize_gmail.py first.")

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    service = build("gmail", "v1", credentials=creds)

    OUT_DIR.mkdir(exist_ok=True)
    EMAILS_DIR.mkdir(parents=True, exist_ok=True)
    ATTACH_DIR.mkdir(parents=True, exist_ok=True)

    q = _build_query(label, query, exclude_from_me=not include_from_me)

    try:
        msg_ids = _list_message_ids(service, "me", query=q, max_results=max_results)
        total = len(msg_ids)
        print(f"Found {total} messages (query={q!r})")

        done = 0
        for msg_id in msg_ids:
            subject = ""
            err: Optional[str] = None
            try:
                full = (
                    service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )

                payload = full.get("payload", {}) or {}
                headers = payload.get("headers", []) or []

                subject = _get_header(headers, "Subject")
                sender = _get_header(headers, "From")
                date = _get_header(headers, "Date")

                body_text = _extract_text_from_payload(payload)
                attachments = _collect_attachments(service, "me", msg_id, payload)

                record = {
                    "id": full.get("id"),
                    "threadId": full.get("threadId"),
                    "labelIds": full.get("labelIds", []),
                    "snippet": full.get("snippet", ""),
                    "subject": subject,
                    "from": sender,
                    "date": date,
                    "body_text": body_text,
                    "attachments": attachments,
                }

                out_path = EMAILS_DIR / f"{msg_id}.json"
                out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

                print(f"- saved {msg_id}: {subject}  attachments={len(attachments)}")
            except Exception as e:
                err = str(e)
                print(f"- failed {msg_id}: {err}")
            finally:
                done += 1
                if progress_cb:
                    progress_cb(done, total, msg_id, subject, err)

        print(f"Done. Output in: {OUT_DIR.resolve()}")
        return {"query": q, "total": total, "saved": total, "out_dir": str(OUT_DIR.resolve())}

    except HttpError as e:
        print("Gmail API error:", e)
        raise


def main(max_results: Optional[int] = 5, query: Optional[str] = None) -> None:
    # 兼容旧用法：只传 query/max_results
    fetch_to_out(label=None, query=query, max_results=max_results, include_from_me=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default=None, help='只拉取该标签下邮件，例如：Support收件')
    ap.add_argument("--query", default=None, help="额外的 Gmail 搜索 query（会与 --label 组合）")
    ap.add_argument(
        "--max-results",
        type=int,
        default=None,
        help="最多拉取多少封（默认：None=全量拉取；可设为 5/100 等）",
    )
    ap.add_argument(
        "--include-from-me",
        action="store_true",
        help="包含我发出的邮件（默认会排除 -from:me -in:sent）",
    )
    args = ap.parse_args()

    fetch_to_out(
        label=args.label,
        query=args.query,
        max_results=args.max_results,
        include_from_me=args.include_from_me,
    )
