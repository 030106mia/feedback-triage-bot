from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import PlainTextResponse
from starlette.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from fetch_full import fetch_to_out
from ai_client import AiError, ai_config_from_settings, analyze_email
from gmail_auth import (
    authorization_url,
    build_flow_for_web,
    credentials_exist,
    delete_token,
    exchange_code_and_save_token,
    token_exists,
)
from jira_client import (
    JiraError,
    create_issue_v2,
    issue_browse_url,
    issue_type_for_classification,
    jira_config_from_dict,
    load_jira_config_from_env,
)
from settings_store import DEFAULT_SETTINGS_PATH, load_settings, merge_settings
from triage_state import DEFAULT_TRIAGE_STATE_DIR, load_state, mark_processed, processing_status, set_jira_link, set_status, upsert_ai_result
from triage_core import (
    discover_input_files,
    load_json,
    load_triage_for_id,
    triage_email_id,
    upsert_triage_fields,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT_DIR / "out"
EMAILS_DIR = OUT_DIR / "emails"
TRIAGE_DIR = OUT_DIR / "triage"
TRIAGE_STATE_DIR = OUT_DIR / "triage_state"
ATTACHMENTS_DIR = OUT_DIR / "attachments"
READ_ONLY = bool(os.getenv("VERCEL")) or (os.getenv("READ_ONLY") == "1")


app = FastAPI(title="Feedback Triage Bot - Web UI")

# Session: “必须由用户点击登录才算已登录”
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("APP_SESSION_SECRET", os.urandom(32).hex()),
    same_site="lax",
    https_only=False,
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["tojson"] = lambda obj, **kwargs: json.dumps(obj, **kwargs)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if ATTACHMENTS_DIR.exists():
    app.mount("/attachments", StaticFiles(directory=str(ATTACHMENTS_DIR)), name="attachments")

@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    # 让本地调试更快：直接把异常文本返回到浏览器（避免只看到 Internal Server Error）
    return PlainTextResponse(f"{type(exc).__name__}: {exc}", status_code=500)

@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    # 产品级体验：401 直接回到登录 Gate；HTMX 请求则返回可读提示
    if exc.status_code == 401:
        if request.headers.get("HX-Request") == "true":
            return HTMLResponse(
                content=(
                    "<div class='p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-900'>"
                    "登录已失效，请先 <a class='underline' href='/'>登录 Gmail</a> 后继续。"
                    "</div>"
                ),
                status_code=401,
            )
        return RedirectResponse(url="/", status_code=302)
    # 其他 HTTP 错误保持 JSON（便于调试）
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


def _gmail_authed(request: Request) -> bool:
    return bool(getattr(request, "session", {}).get("gmail_authed"))


def _require_gmail_login(request: Request) -> None:
    if not _gmail_authed(request):
        raise HTTPException(status_code=401, detail="Not logged in")


@dataclass
class EmailListItem:
    email_id: str
    subject: str
    from_email: str
    from_name: str
    date: str
    date_display: str
    has_attachments: bool
    mtime: float
    triage_exists: bool
    status: str  # legacy/raw
    processing_status: str


def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    try:
        return str(x)
    except Exception:
        return ""


def _format_date_display(raw_date: str, mtime: float) -> str:
    """
    首页时间显示：YYYY-MM-DD HH:MM
    优先解析 Gmail Date header；失败则用文件 mtime。
    """
    try:
        if raw_date:
            dt = parsedate_to_datetime(raw_date)
            if dt is not None:
                # 保留时区信息的本地表示可能不一致，这里统一转为 naive 的本地时间字符串不好做；
                # MVP：直接用 dt 的年月日时分（dt 若带 tz，strftime 会按本地转换或保留，足够用于“时间点”展示）。
                return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass

    dt2 = datetime.fromtimestamp(mtime)
    return dt2.strftime("%Y-%m-%d %H:%M")

def _labels_from_text(text: str) -> List[str]:
    parts = [p.strip() for p in (text or "").replace("\n", ",").split(",")]
    out: List[str] = []
    for p in parts:
        if not p:
            continue
        if p not in out:
            out.append(p)
    return out


def _jira_issue_type_options() -> List[str]:
    # 仅用于 UI 下拉；真正创建时仍会校验完整配置
    try:
        settings = load_settings(path=str(OUT_DIR / "settings.json"))
        if isinstance(settings.get("jira"), dict):
            cfg = jira_config_from_dict(settings["jira"])
            return [cfg.issue_type_bug, cfg.issue_type_task]
    except Exception:
        pass
    try:
        cfg = load_jira_config_from_env()
        return [cfg.issue_type_bug, cfg.issue_type_task]
    except Exception:
        return ["Bug", "Task"]


def _jira_defaults_for_email(email: Dict[str, Any], st: Dict[str, Any], issue_type_options: List[str]) -> Dict[str, str]:
    subject = _safe_str(email.get("subject") or "").strip() or "(no subject)"
    from_ = _safe_str(email.get("from") or "").strip()
    date = _safe_str(email.get("date") or "").strip()
    snippet = _safe_str(email.get("snippet") or "").strip()
    body = _safe_str(email.get("body_text") or "").strip()

    ai = st.get("ai") if isinstance(st.get("ai"), dict) else {}
    ai_decision = _safe_str(ai.get("decision") or "")
    ai_reason = _safe_str(ai.get("reason") or "")
    raw = ai.get("raw") if isinstance(ai.get("raw"), dict) else {}
    signals = raw.get("signals") if isinstance(raw.get("signals"), list) else []
    sig_lines = "\n".join([f"- {_safe_str(s)}" for s in signals if _safe_str(s)])

    description = "\n".join(
        [
            f"From: {from_}" if from_ else "From: (unknown)",
            f"Date: {date}" if date else "Date: -",
            "",
            "Snippet:",
            snippet or "",
            "",
            "Body:",
            body or "",
            "",
            "AI:",
            f"decision: {ai_decision}" if ai_decision else "decision: -",
            ai_reason or "",
            ("signals:\n" + sig_lines) if sig_lines else "signals: []",
        ]
    ).strip()

    default_issue_type = issue_type_options[1] if len(issue_type_options) > 1 else (issue_type_options[0] if issue_type_options else "Task")

    return {
        "issue_type_name": default_issue_type,
        "summary": subject,
        "description": description,
        "labels": "",
    }


def _triage_path(email_id: str) -> Path:
    return TRIAGE_DIR / f"{email_id}.triage.json"


def _status_for_email(email_id: str) -> str:
    st = load_state(email_id, state_dir=str(TRIAGE_STATE_DIR))
    if isinstance(st, dict) and st.get("status"):
        return str(st.get("status"))
    return "todo"


def _is_candidate(triage: Optional[Dict[str, Any]]) -> bool:
    """
    “值得进 Jira”候选：只基于现有 triage 结果，不修改 triage 能力。
    MVP：bug / feature_request / account_support 视为候选。
    """
    if not triage:
        return False
    c = (triage.get("classification") or "").strip()
    return c in {"bug", "feature_request", "account_support"}


def _parse_email_file(path: str) -> Tuple[EmailListItem, Dict[str, Any]]:
    """
    返回 (列表展示字段, 完整 email dict)。尽量容错：坏 JSON 也能显示占位。
    """
    mtime = 0.0
    try:
        mtime = os.path.getmtime(path)
    except Exception:
        pass

    email_id = os.path.splitext(os.path.basename(path))[0]
    email: Dict[str, Any] = {}
    try:
        email = load_json(path)
        email_id = _safe_str(email.get("id") or email.get("email_id") or email_id) or email_id
    except Exception as e:
        email = {"id": email_id, "subject": "(bad json)", "from": "", "date": "", "snippet": str(e), "body_text": ""}

    subject = _safe_str(email.get("subject")) or "(no subject)"
    from_email = _safe_str(email.get("from") or email.get("from_email") or email.get("sender")) or "(unknown)"
    # from_name: 仅用于展示（不影响原始字段）
    try:
        from email.utils import parseaddr
        name, addr = parseaddr(from_email)
        from_name = name or addr or from_email
    except Exception:
        from_name = from_email
    date = _safe_str(email.get("date")) or ""
    date_display = _format_date_display(date, mtime)
    attachments = email.get("attachments")
    has_attachments = isinstance(attachments, list) and len(attachments) > 0
    triage_exists = _triage_path(email_id).exists()
    raw_status = _status_for_email(email_id)
    st = load_state(email_id, state_dir=str(TRIAGE_STATE_DIR))
    pstatus = processing_status(st)

    item = EmailListItem(
        email_id=email_id,
        subject=subject,
        from_email=from_email,
        from_name=from_name,
        date=date,
        date_display=date_display,
        has_attachments=has_attachments,
        mtime=mtime,
        triage_exists=triage_exists,
        status=raw_status,
        processing_status=pstatus,
    )
    return item, email


def list_email_items(limit: Optional[int] = None) -> List[EmailListItem]:
    if not EMAILS_DIR.exists():
        return []
    files = discover_input_files(str(EMAILS_DIR / "*.json"))
    items: List[EmailListItem] = []
    for p in files:
        item, _ = _parse_email_file(p)
        items.append(item)
        if limit is not None and len(items) >= limit:
            break
    return items


def load_email_by_id(email_id: str) -> Dict[str, Any]:
    path = EMAILS_DIR / f"{email_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Email not found: {email_id}")
    try:
        return load_json(str(path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read email json: {e}")


def _labels_from_text(raw: str) -> List[str]:
    # 支持逗号/换行分隔
    parts: List[str] = []
    for chunk in raw.replace("\r", "\n").split("\n"):
        parts.extend(chunk.split(","))
    labels = [p.strip() for p in parts if p.strip()]
    # 去重但保持顺序
    out: List[str] = []
    seen = set()
    for l in labels:
        if l not in seen:
            out.append(l)
            seen.add(l)
    return out


# ----------------------------
# Pages
# ----------------------------


@app.get("/", response_class=HTMLResponse, name="home")
def home(request: Request) -> HTMLResponse:
    # 登录 Gate：未登录只显示登录引导页
    if not _gmail_authed(request):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "token_exists": token_exists(), "error": None},
        )
    return RedirectResponse(url="/app", status_code=302)


@app.get("/app", response_class=HTMLResponse, name="app_home")
def app_home(request: Request) -> HTMLResponse:
    _require_gmail_login(request)
    return templates.TemplateResponse("app.html", {"request": request})


@app.get("/auth/gmail", name="auth_gmail_start")
def auth_gmail_start(request: Request):
    """
    必须由用户点击触发：
    - 若 token 已存在：视为已授权，设置会话为已登录，进入主流程
    - 若 token 不存在：走 OAuth，回调后写入 token，再进入主流程
    """
    if token_exists():
        request.session["gmail_authed"] = True
        return RedirectResponse(url="/app", status_code=302)

    if not credentials_exist():
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "token_exists": False, "error": "缺少 secrets/gmail_credentials.json，无法发起 OAuth。"},
        )

    redirect_uri = str(request.url_for("auth_gmail_callback"))
    flow = build_flow_for_web(redirect_uri=redirect_uri)
    request.session["oauth_state"] = flow.state
    return RedirectResponse(url=authorization_url(flow), status_code=302)


@app.get("/auth/gmail/callback", name="auth_gmail_callback")
def auth_gmail_callback(request: Request, code: str | None = None, state: str | None = None):
    if not code:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "token_exists": token_exists(), "error": "OAuth 回调缺少 code。"},
        )
    expected = request.session.get("oauth_state")
    if expected and state and state != expected:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "token_exists": token_exists(), "error": "OAuth state 不匹配，请重试登录。"},
        )

    try:
        redirect_uri = str(request.url_for("auth_gmail_callback"))
        flow = build_flow_for_web(redirect_uri=redirect_uri, state=state)
        exchange_code_and_save_token(flow, code)
    except Exception as e:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "token_exists": token_exists(), "error": f"OAuth 失败：{e}"},
        )

    request.session["gmail_authed"] = True
    return RedirectResponse(url="/app", status_code=302)


@app.post("/auth/gmail/logout", name="auth_gmail_logout")
def auth_gmail_logout(request: Request):
    """
    退出 Gmail 登录：删除 token 并回到 Gate
    """
    try:
        delete_token()
    except Exception:
        pass
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)


def _home_counts(emails: List[EmailListItem]) -> Dict[str, int]:
    counts = {"all": len(emails), "todo": 0, "jira": 0, "skip": 0, "done": 0, "candidate": 0}
    for e in emails:
        if e.status in counts:
            counts[e.status] += 1
    # candidate 需要 triage 才能判断：只统计 todo 中已 triage 且候选
    cand = 0
    for e in emails:
        if e.status != "todo":
            continue
        triage = load_triage_for_id(e.email_id, triage_dir=str(TRIAGE_DIR))
        if _is_candidate(triage):
            cand += 1
    counts["candidate"] = cand
    return counts


@app.get("/email/{email_id}", response_class=HTMLResponse, name="email_detail")
def email_detail(request: Request, email_id: str) -> HTMLResponse:
    _require_gmail_login(request)
    email = load_email_by_id(email_id)
    return templates.TemplateResponse(
        "email_view.html",
        {
            "request": request,
            "email_id": email_id,
            "email": email,
        },
    )


@app.get("/email/{email_id}/triage", response_class=HTMLResponse, name="email_triage")
def email_triage(request: Request, email_id: str) -> HTMLResponse:
    """
    保留原有 triage 能力（但不作为主工作流页面）。
    """
    _require_gmail_login(request)
    email = load_email_by_id(email_id)
    triage = load_triage_for_id(email_id, triage_dir=str(TRIAGE_DIR))
    status = _status_for_email(email_id)
    return templates.TemplateResponse(
        "email_detail.html",
        {"request": request, "email_id": email_id, "email": email, "triage": triage, "status": status},
    )

@app.get("/emails", response_class=HTMLResponse, name="emails_page")
def emails_page(
    request: Request,
    q: str = "",
    status: str = "active",  # active(pending+ignore)/pending/ignore/processed/all
    date_from: str = "",
    date_to: str = "",
    page: int = 1,
) -> HTMLResponse:
    _require_gmail_login(request)
    """
    邮件列表（50/页），支持搜索/筛选状态/筛选时间。
    默认不显示已处理（status=pending）。
    """
    page_size = 50
    page = max(1, int(page or 1))
    emails = list_email_items()

    # filters
    q_norm = (q or "").strip().lower()
    filtered: List[EmailListItem] = []
    for e in emails:
        if status == "active":
            if e.processing_status not in {"pending", "ignore"}:
                continue
        elif status != "all" and e.processing_status != status:
            continue
        if q_norm:
            hay = f"{e.subject} {e.from_name} {e.from_email}".lower()
            if q_norm not in hay:
                continue
        # 时间筛选（基于 date_display 的字符串比较不稳；MVP 用 mtime）
        if date_from:
            try:
                # 支持 datetime-local: "YYYY-MM-DDTHH:MM"
                df = datetime.fromisoformat(date_from)
                if datetime.fromtimestamp(e.mtime) < df:
                    continue
            except Exception:
                pass
        if date_to:
            try:
                dt = datetime.fromisoformat(date_to)
                if datetime.fromtimestamp(e.mtime) > dt:
                    continue
            except Exception:
                pass
        filtered.append(e)

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = filtered[start:end]
    total_pages = max(1, (total + page_size - 1) // page_size)

    return templates.TemplateResponse(
        "emails.html",
        {
            "request": request,
            "emails": page_items,
            "q": q,
            "status": status,
            "date_from": date_from,
            "date_to": date_to,
            "page": page,
            "total": total,
            "total_pages": total_pages,
            "page_size": page_size,
        },
    )


@app.post("/api/email/{email_id}/process", response_class=HTMLResponse, name="api_email_process")
async def api_email_process(request: Request, email_id: str) -> HTMLResponse:
    """
    列表上的一键“处理”：标记为已处理，并从默认列表中消失（HTMX delete swap）。
    """
    _require_gmail_login(request)
    if READ_ONLY:
        raise HTTPException(status_code=403, detail="只读模式下不允许写入状态。")
    await asyncio.to_thread(mark_processed, email_id, state_dir=str(TRIAGE_STATE_DIR))
    return HTMLResponse(content="", status_code=204)

@app.get("/process/{email_id}", response_class=HTMLResponse, name="process_email")
def process_email(request: Request, email_id: str) -> HTMLResponse:
    _require_gmail_login(request)
    email = load_email_by_id(email_id)
    st = load_state(email_id, state_dir=str(TRIAGE_STATE_DIR)) or {}
    pstatus = processing_status(st)
    issue_types = _jira_issue_type_options()
    jira_defaults = _jira_defaults_for_email(email, st, issue_types)
    return templates.TemplateResponse(
        "process_email.html",
        {
            "request": request,
            "email_id": email_id,
            "email": email,
            "state": st,
            "processing_status": pstatus,
            "read_only": READ_ONLY,
            "jira_issue_types": issue_types,
            "jira_defaults": jira_defaults,
            "error": None,
        },
    )


@app.get("/partials/fetch_modal", response_class=HTMLResponse, name="partial_fetch_modal")
def partial_fetch_modal(request: Request) -> HTMLResponse:
    _require_gmail_login(request)
    settings = load_settings(path=str(OUT_DIR / "settings.json"))
    gmail = settings.get("gmail") if isinstance(settings.get("gmail"), dict) else {}
    label = str(gmail.get("label") or "").strip()
    return templates.TemplateResponse("partials/fetch_modal.html", {"request": request, "label": label})


@app.get("/partials/close_modal", response_class=HTMLResponse, name="partial_close_modal")
def partial_close_modal(request: Request) -> HTMLResponse:
    return HTMLResponse(content="", status_code=200)


@app.get("/triage", response_class=HTMLResponse, name="triage_batch_page")
def triage_batch_page(request: Request, limit: int = 5) -> HTMLResponse:
    _require_gmail_login(request)
    return templates.TemplateResponse("triage_batch.html", {"request": request, "limit": limit})


@app.get("/fetch", response_class=HTMLResponse, name="gmail_fetch_page")
def gmail_fetch_page(request: Request, label: str = "Support收件") -> HTMLResponse:
    # 兼容旧入口：统一跳回主流程（手动拉取在 /app 的弹层里）
    if not _gmail_authed(request):
        return RedirectResponse(url="/", status_code=302)
    return RedirectResponse(url="/app", status_code=302)


@app.get("/work", response_class=HTMLResponse, name="work_page")
def work_page(request: Request, scope: str = "candidate") -> HTMLResponse:
    _require_gmail_login(request)
    """
    快速处理页：默认只处理“候选”（值得进 Jira）且未处理的邮件。
    scope:
      - candidate: triage.classification 命中候选集合的 todo 邮件
      - todo: 所有未处理邮件
    """
    email_id = _pick_next_email_id(scope=scope)
    if not email_id:
        return templates.TemplateResponse(
            "work.html",
            {"request": request, "scope": scope, "email_id": None, "email": None, "triage": None, "error": None},
        )

    email = load_email_by_id(email_id)
    triage = load_triage_for_id(email_id, triage_dir=str(TRIAGE_DIR))
    if not triage:
        # 自动补齐 triage，减少“打开就得点 Run”的操作
        triage = triage_email_id(email_id, str(EMAILS_DIR), str(TRIAGE_DIR))

    return templates.TemplateResponse(
        "work.html",
        {"request": request, "scope": scope, "email_id": email_id, "email": email, "triage": triage, "error": None},
    )


@app.get("/settings", response_class=HTMLResponse, name="settings_page")
def settings_page(request: Request) -> HTMLResponse:
    _require_gmail_login(request)
    settings = load_settings(path=str(OUT_DIR / "settings.json"))
    gmail = settings.get("gmail") if isinstance(settings.get("gmail"), dict) else {}
    jira = settings.get("jira") if isinstance(settings.get("jira"), dict) else {}
    ai = settings.get("ai") if isinstance(settings.get("ai"), dict) else {}
    prompt = settings.get("prompt") or ""
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "gmail": gmail,
            "jira": jira,
            "ai": ai,
            "prompt": prompt,
            "saved": None,
            "error": None,
            "settings_path": str(OUT_DIR / "settings.json"),
            "read_only": READ_ONLY,
        },
    )


@app.post("/api/settings/save", response_class=HTMLResponse, name="api_settings_save")
async def api_settings_save(
    request: Request,
    gmail_label: str = Form(""),
    jira_base_url: str = Form(""),
    jira_email: str = Form(""),
    jira_api_token: str = Form(""),
    jira_project_key: str = Form(""),
    jira_issue_type_bug: str = Form("缺陷"),
    jira_issue_type_task: str = Form("任务"),
    ai_provider: str = Form(""),
    ai_base_url: str = Form(""),
    ai_api_key: str = Form(""),
    ai_model: str = Form(""),
    prompt: str = Form(""),
) -> HTMLResponse:
    _require_gmail_login(request)
    if READ_ONLY:
        settings = load_settings(path=str(OUT_DIR / "settings.json"))
        jira = settings.get("jira") if isinstance(settings.get("jira"), dict) else {}
        ai = settings.get("ai") if isinstance(settings.get("ai"), dict) else {}
        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "jira": jira,
                "ai": ai,
                "saved": None,
                "error": "当前处于只读模式（例如 Vercel Serverless）。请在 Vercel 项目里配置环境变量，或在本地运行以保存到 out/settings.json。",
                "settings_path": str(OUT_DIR / "settings.json"),
                "read_only": READ_ONLY,
            },
        )

    try:
        merge_settings(
            {
                "gmail": {"label": gmail_label.strip()},
                "jira": {
                    "base_url": jira_base_url.strip(),
                    "email": jira_email.strip(),
                    "api_token": jira_api_token.strip(),
                    "project_key": jira_project_key.strip(),
                    "issue_type_bug": jira_issue_type_bug.strip(),
                    "issue_type_task": jira_issue_type_task.strip(),
                },
                "ai": {
                    "provider": ai_provider.strip(),
                    "base_url": ai_base_url.strip(),
                    "api_key": ai_api_key.strip(),
                    "model": ai_model.strip(),
                },
                "prompt": prompt,
            },
            path=str(OUT_DIR / "settings.json"),
        )
    except Exception as e:
        settings = load_settings(path=str(OUT_DIR / "settings.json"))
        gmail = settings.get("gmail") if isinstance(settings.get("gmail"), dict) else {}
        jira = settings.get("jira") if isinstance(settings.get("jira"), dict) else {}
        ai = settings.get("ai") if isinstance(settings.get("ai"), dict) else {}
        prompt_cur = settings.get("prompt") or ""
        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "gmail": gmail,
                "jira": jira,
                "ai": ai,
                "prompt": prompt_cur,
                "saved": None,
                "error": str(e),
                "settings_path": str(OUT_DIR / "settings.json"),
                "read_only": READ_ONLY,
            },
        )

    settings = load_settings(path=str(OUT_DIR / "settings.json"))
    gmail = settings.get("gmail") if isinstance(settings.get("gmail"), dict) else {}
    jira = settings.get("jira") if isinstance(settings.get("jira"), dict) else {}
    ai = settings.get("ai") if isinstance(settings.get("ai"), dict) else {}
    prompt_cur = settings.get("prompt") or ""
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "gmail": gmail,
            "jira": jira,
            "ai": ai,
            "prompt": prompt_cur,
            "saved": "已保存",
            "error": None,
            "settings_path": str(OUT_DIR / "settings.json"),
            "read_only": READ_ONLY,
        },
    )


def _pick_next_email_id(scope: str) -> Optional[str]:
    emails = list_email_items()
    for e in emails:
        if e.status != "todo":
            continue
        if scope == "todo":
            return e.email_id
        # candidate
        triage = load_triage_for_id(e.email_id, triage_dir=str(TRIAGE_DIR))
        if not triage:
            # 没 triage 的先不判定候选（会在 work 页面自动 triage）
            continue
        if _is_candidate(triage):
            return e.email_id
    # candidate 队列为空时，fallback 到 todo
    if scope == "candidate":
        for e in emails:
            if e.status == "todo":
                return e.email_id
    return None


# ----------------------------
# HTMX APIs
# ----------------------------


@app.post("/api/triage/run/{email_id}", response_class=HTMLResponse, name="api_triage_run")
async def api_triage_run(request: Request, email_id: str) -> HTMLResponse:
    _require_gmail_login(request)
    if READ_ONLY:
        return templates.TemplateResponse(
            "partials/triage_section.html",
            {"request": request, "email_id": email_id, "triage": None, "error": "只读模式下不允许写入 out/triage。请本地运行。"},
        )
    # 用线程避免阻塞 event loop（未来 triage 如果变重也更稳）
    try:
        triage = await asyncio.to_thread(triage_email_id, email_id, str(EMAILS_DIR), str(TRIAGE_DIR))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Email not found: {email_id}")
    except Exception as e:
        return templates.TemplateResponse(
            "partials/triage_section.html",
            {"request": request, "email_id": email_id, "triage": None, "error": str(e)},
        )

    return templates.TemplateResponse(
        "partials/triage_section.html",
        {"request": request, "email_id": email_id, "triage": triage, "error": None},
    )


@app.post("/api/triage/save/{email_id}", response_class=HTMLResponse, name="api_triage_save")
async def api_triage_save(
    request: Request,
    email_id: str,
    classification: str = Form("other"),
    priority: str = Form("P3"),
    jira_summary: str = Form(""),
    jira_description: str = Form(""),
    jira_labels: str = Form(""),
) -> HTMLResponse:
    _require_gmail_login(request)
    if READ_ONLY:
        return templates.TemplateResponse(
            "partials/triage_section.html",
            {"request": request, "email_id": email_id, "triage": None, "error": "只读模式下不允许保存 triage。请本地运行。"},
        )
    labels = _labels_from_text(jira_labels)
    try:
        triage = await asyncio.to_thread(
            upsert_triage_fields,
            email_id,
            classification.strip(),
            priority.strip(),
            jira_summary,
            jira_description,
            labels,
            str(TRIAGE_DIR),
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partials/triage_section.html",
            {"request": request, "email_id": email_id, "triage": None, "error": str(e)},
        )

    return templates.TemplateResponse(
        "partials/triage_section.html",
        {"request": request, "email_id": email_id, "triage": triage, "error": None},
    )


@app.post("/api/state/set/{email_id}", response_class=HTMLResponse, name="api_state_set")
async def api_state_set(
    request: Request,
    email_id: str,
    status: str = Form("todo"),
    reason: str = Form(""),
) -> HTMLResponse:
    _require_gmail_login(request)
    if READ_ONLY:
        return templates.TemplateResponse(
            "partials/status_badge.html",
            {"request": request, "status": "todo"},
        )
    # 仅写状态层，不改 triage 能力/拉取逻辑
    try:
        await asyncio.to_thread(set_status, email_id, status, state_dir=str(TRIAGE_STATE_DIR), reason=reason)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 返回一个小 badge（供 work/index 局部刷新）
    return templates.TemplateResponse(
        "partials/status_badge.html",
        {"request": request, "status": status},
    )

@app.post("/api/process/mark/{email_id}", response_class=HTMLResponse, name="api_process_mark")
async def api_process_mark(
    request: Request,
    email_id: str,
    mark: str = Form("processed"),  # processed/ignore
) -> HTMLResponse:
    _require_gmail_login(request)
    if READ_ONLY:
        raise HTTPException(status_code=403, detail="只读模式下不允许写入状态。")
    if mark not in {"processed", "ignore"}:
        mark = "processed"
    await asyncio.to_thread(set_status, email_id, mark, state_dir=str(TRIAGE_STATE_DIR))
    email = load_email_by_id(email_id)
    st = load_state(email_id, state_dir=str(TRIAGE_STATE_DIR)) or {}
    pstatus = processing_status(st)
    issue_types = _jira_issue_type_options()
    jira_defaults = _jira_defaults_for_email(email, st, issue_types)
    if request.headers.get("HX-Request") != "true":
        return RedirectResponse(url=f"/process/{email_id}", status_code=302)
    return templates.TemplateResponse(
        "partials/process_panel.html",
        {
            "request": request,
            "email_id": email_id,
            "email": email,
            "state": st,
            "processing_status": pstatus,
            "read_only": READ_ONLY,
            "jira_issue_types": issue_types,
            "jira_defaults": jira_defaults,
            "error": None,
        },
    )


@app.post("/api/process/jira/{email_id}", response_class=HTMLResponse, name="api_process_jira")
async def api_process_jira(
    request: Request,
    email_id: str,
    issue_type_name: str = Form(""),
    summary: str = Form(""),
    description: str = Form(""),
    labels: str = Form(""),
) -> HTMLResponse:
    _require_gmail_login(request)
    if READ_ONLY:
        raise HTTPException(status_code=403, detail="只读模式下不允许创建 Jira/写入状态。请本地运行。")

    email = load_email_by_id(email_id)
    st = load_state(email_id, state_dir=str(TRIAGE_STATE_DIR)) or {}
    pstatus = processing_status(st)
    issue_types = _jira_issue_type_options()
    jira_defaults = _jira_defaults_for_email(email, st, issue_types)

    # 仅允许对待处理推进 Jira（避免重复/误点）
    if pstatus != "pending":
        if request.headers.get("HX-Request") != "true":
            return RedirectResponse(url=f"/process/{email_id}", status_code=302)
        return templates.TemplateResponse(
            "partials/process_panel.html",
            {
                "request": request,
                "email_id": email_id,
                "email": email,
                "state": st,
                "processing_status": pstatus,
                "read_only": READ_ONLY,
                "jira_issue_types": issue_types,
                "jira_defaults": jira_defaults,
                "error": "当前状态不是“待处理”，不允许创建 Jira。",
            },
        )

    try:
        settings = load_settings(path=str(OUT_DIR / "settings.json"))
        cfg = None
        if isinstance(settings.get("jira"), dict):
            try:
                cfg = jira_config_from_dict(settings["jira"])
            except JiraError:
                cfg = None
        if cfg is None:
            cfg = load_jira_config_from_env()

        labels_list = _labels_from_text(labels)
        issue_type = (issue_type_name or "").strip() or issue_types[0]
        created = await asyncio.to_thread(
            create_issue_v2,
            cfg,
            summary=(summary or "").strip(),
            description=description or "",
            labels=labels_list,
            issue_type_name=issue_type,
        )
        issue_key = str(created.get("key") or "")
        if not issue_key:
            raise JiraError(f"Jira response missing key: {created}")
        jira_url = issue_browse_url(cfg, issue_key)
        await asyncio.to_thread(set_jira_link, email_id, jira_key=issue_key, jira_url=jira_url, state_dir=str(TRIAGE_STATE_DIR))
        st = load_state(email_id, state_dir=str(TRIAGE_STATE_DIR)) or st
        pstatus = processing_status(st)
    except Exception as e:
        if request.headers.get("HX-Request") != "true":
            return RedirectResponse(url=f"/process/{email_id}", status_code=302)
        # 保持用户输入（用本次提交覆盖 defaults）
        jira_defaults = {
            "issue_type_name": (issue_type_name or jira_defaults.get("issue_type_name") or "").strip(),
            "summary": summary or "",
            "description": description or "",
            "labels": labels or "",
        }
        return templates.TemplateResponse(
            "partials/process_panel.html",
            {
                "request": request,
                "email_id": email_id,
                "email": email,
                "state": st,
                "processing_status": pstatus,
                "read_only": READ_ONLY,
                "jira_issue_types": issue_types,
                "jira_defaults": jira_defaults,
                "error": f"创建 Jira 失败：{e}（请先在 /settings 配置 Jira）",
            },
        )

    if request.headers.get("HX-Request") != "true":
        return RedirectResponse(url=f"/process/{email_id}", status_code=302)
    # 成功：刷新右侧面板，展示 Jira 链接 + 已处理状态
    jira_defaults = _jira_defaults_for_email(email, st, issue_types)
    return templates.TemplateResponse(
        "partials/process_panel.html",
        {
            "request": request,
            "email_id": email_id,
            "email": email,
            "state": st,
            "processing_status": pstatus,
            "read_only": READ_ONLY,
            "jira_issue_types": issue_types,
            "jira_defaults": jira_defaults,
            "error": None,
        },
    )


class FetchParseJob:
    def __init__(self, job_id: str, limit: int):
        self.job_id = job_id
        self.limit = limit
        self.total = 0
        self.done = 0
        self.error: Optional[str] = None
        self.finished_at: Optional[str] = None

    @property
    def finished(self) -> bool:
        return self.finished_at is not None


FETCH_PARSE_JOBS: Dict[str, FetchParseJob] = {}


async def _run_fetch_parse(job: FetchParseJob, label: str) -> None:
    try:
        settings = load_settings(path=str(OUT_DIR / "settings.json"))
        cfg = ai_config_from_settings(settings)

        fetched_ids: List[str] = []

        def on_progress(done: int, total: int, msg_id: str, subject: str, error: Optional[str]) -> None:
            job.done = done
            job.total = total
            if msg_id:
                fetched_ids.append(msg_id)

        await asyncio.to_thread(
            fetch_to_out,
            label=label or None,
            query=None,
            max_results=job.limit,
            include_from_me=False,
            progress_cb=on_progress,
        )

        # 解析：对本次拉到的 msg_id 逐个调用 AI
        for mid in fetched_ids:
            try:
                email = load_email_by_id(mid)
                out = analyze_email(cfg, email)
                result = str(out.get("result") or "").strip()
                decision = "ignore" if result == "无需处理" else "pending"
                reason = str(out.get("reason") or "")
                upsert_ai_result(mid, decision=decision, reason=reason, raw=out, state_dir=str(TRIAGE_STATE_DIR))
            except Exception as e:
                upsert_ai_result(mid, decision="pending", reason=f"AI 解析失败：{e}", raw={"error": str(e)}, state_dir=str(TRIAGE_STATE_DIR))

    except Exception as e:
        job.error = str(e)
    finally:
        job.finished_at = datetime.utcnow().isoformat() + "Z"


@app.post("/api/fetch_parse/start", response_class=HTMLResponse, name="api_fetch_parse_start")
async def api_fetch_parse_start(
    request: Request,
    label: str = Form(""),
    limit: int = Form(50),
) -> HTMLResponse:
    _require_gmail_login(request)
    if READ_ONLY:
        raise HTTPException(status_code=403, detail="只读模式下不允许拉取/解析。")
    limit = max(1, min(int(limit or 50), 500))
    settings = load_settings(path=str(OUT_DIR / "settings.json"))
    gmail = settings.get("gmail") if isinstance(settings.get("gmail"), dict) else {}
    label = (label or "").strip() or str(gmail.get("label") or "").strip()

    job_id = uuid.uuid4().hex
    job = FetchParseJob(job_id=job_id, limit=limit)
    FETCH_PARSE_JOBS[job_id] = job
    asyncio.create_task(_run_fetch_parse(job, label))
    return templates.TemplateResponse("partials/fetch_parse_status.html", {"request": request, "job": job})


@app.get("/api/fetch_parse/status/{job_id}", response_class=HTMLResponse, name="api_fetch_parse_status")
def api_fetch_parse_status(request: Request, job_id: str) -> HTMLResponse:
    _require_gmail_login(request)
    job = FETCH_PARSE_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return templates.TemplateResponse("partials/fetch_parse_status.html", {"request": request, "job": job})


@app.post("/api/work/decide/{email_id}", response_class=HTMLResponse, name="api_work_decide")
async def api_work_decide(
    request: Request,
    email_id: str,
    decision: str = Form("jira"),  # jira/skip/done
    scope: str = Form("candidate"),
    classification: str = Form("other"),
    priority: str = Form("P3"),
    jira_summary: str = Form(""),
    jira_description: str = Form(""),
    jira_labels: str = Form(""),
) -> HTMLResponse:
    _require_gmail_login(request)
    if READ_ONLY:
        raise HTTPException(status_code=403, detail="只读模式下不允许创建 Jira/写入状态。请本地运行。")
    # 1) 保存 triage 字段（允许快速修订）
    labels = _labels_from_text(jira_labels)
    try:
        await asyncio.to_thread(
            upsert_triage_fields,
            email_id,
            classification.strip(),
            priority.strip(),
            jira_summary,
            jira_description,
            labels,
            str(TRIAGE_DIR),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"save triage failed: {e}")

    # 2) 若 decision=jira，则创建 Jira issue（失败则留在当前页显示错误）
    if decision not in {"jira", "skip", "done"}:
        decision = "jira"

    if decision == "jira":
        try:
            # 优先从设置读取；没有再 fallback 环境变量
            settings = load_settings(path=str(OUT_DIR / "settings.json"))
            cfg = None
            if isinstance(settings.get("jira"), dict):
                try:
                    cfg = jira_config_from_dict(settings["jira"])
                except JiraError:
                    cfg = None
            if cfg is None:
                cfg = load_jira_config_from_env()

            issue_type_name = issue_type_for_classification(cfg, classification.strip())
            created = await asyncio.to_thread(
                create_issue_v2,
                cfg,
                summary=jira_summary,
                description=jira_description,
                labels=labels,
                issue_type_name=issue_type_name,
            )
            issue_key = str(created.get("key") or "")
            if not issue_key:
                raise JiraError(f"Jira response missing key: {created}")
            jira_url = issue_browse_url(cfg, issue_key)
            await asyncio.to_thread(set_jira_link, email_id, jira_key=issue_key, jira_url=jira_url, state_dir=str(TRIAGE_STATE_DIR))
        except Exception as e:
            # 保持在当前 email，让你修订/重试
            email = load_email_by_id(email_id)
            triage = load_triage_for_id(email_id, triage_dir=str(TRIAGE_DIR))
            return templates.TemplateResponse(
                "partials/work_item.html",
                {
                    "request": request,
                    "scope": scope,
                    "email_id": email_id,
                    "email": email,
                    "triage": triage,
                    "error": f"创建 Jira 失败：{e}（请先在 /settings 配置 Jira）",
                },
            )
    else:
        # skip/done
        await asyncio.to_thread(set_status, email_id, decision, state_dir=str(TRIAGE_STATE_DIR))

    # 3) 返回下一封（局部刷新整个 work item）
    next_id = _pick_next_email_id(scope=scope)
    if not next_id:
        return templates.TemplateResponse(
            "partials/work_item.html",
            {"request": request, "scope": scope, "email_id": None, "email": None, "triage": None},
        )

    email = load_email_by_id(next_id)
    triage = load_triage_for_id(next_id, triage_dir=str(TRIAGE_DIR))
    if not triage:
        triage = await asyncio.to_thread(triage_email_id, next_id, str(EMAILS_DIR), str(TRIAGE_DIR))

    return templates.TemplateResponse(
        "partials/work_item.html",
        {"request": request, "scope": scope, "email_id": next_id, "email": email, "triage": triage, "error": None},
    )


# ----------------------------
# Batch triage jobs (in-memory)
# ----------------------------


class BatchJob:
    def __init__(self, job_id: str, email_ids: List[str]):
        self.job_id = job_id
        self.email_ids = email_ids
        self.total = len(email_ids)
        self.done = 0
        self.started_at = datetime.utcnow().isoformat() + "Z"
        self.finished_at: Optional[str] = None
        self.results: List[Dict[str, Any]] = []

    @property
    def finished(self) -> bool:
        return self.finished_at is not None


JOBS: Dict[str, BatchJob] = {}


async def _run_batch(job: BatchJob) -> None:
    for email_id in job.email_ids:
        try:
            triage = await asyncio.to_thread(triage_email_id, email_id, str(EMAILS_DIR), str(TRIAGE_DIR))
            job.results.append({"email_id": email_id, "ok": True, "error": None, "triage": triage})
        except Exception as e:
            job.results.append({"email_id": email_id, "ok": False, "error": str(e), "triage": None})
        job.done += 1
    job.finished_at = datetime.utcnow().isoformat() + "Z"


@app.post("/api/triage/batch/start", response_class=HTMLResponse, name="api_batch_start")
async def api_batch_start(request: Request, limit: int = Form(5)) -> HTMLResponse:
    limit = int(limit) if limit else 5
    limit = max(1, min(limit, 200))

    email_items = list_email_items(limit=limit)
    email_ids = [e.email_id for e in email_items]

    job_id = uuid.uuid4().hex
    job = BatchJob(job_id=job_id, email_ids=email_ids)
    JOBS[job_id] = job

    asyncio.create_task(_run_batch(job))

    return templates.TemplateResponse(
        "partials/batch_status.html",
        {"request": request, "job": job},
    )


@app.get("/api/triage/batch/status/{job_id}", response_class=HTMLResponse, name="api_batch_status")
def api_batch_status(request: Request, job_id: str) -> HTMLResponse:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return templates.TemplateResponse("partials/batch_status.html", {"request": request, "job": job})


# ----------------------------
# Gmail fetch jobs (in-memory)
# ----------------------------


class FetchJob:
    def __init__(self, job_id: str, label: str, max_results: Optional[int], include_from_me: bool):
        self.job_id = job_id
        self.label = label
        self.max_results = max_results
        self.include_from_me = include_from_me
        self.total = 0
        self.done = 0
        self.started_at = datetime.utcnow().isoformat() + "Z"
        self.finished_at: Optional[str] = None
        self.error: Optional[str] = None

    @property
    def finished(self) -> bool:
        return self.finished_at is not None


FETCH_JOBS: Dict[str, FetchJob] = {}


async def _run_fetch(job: FetchJob) -> None:
    def on_progress(done: int, total: int, msg_id: str, subject: str, error: Optional[str]) -> None:
        job.done = done
        job.total = total

    try:
        await asyncio.to_thread(
            fetch_to_out,
            label=job.label,
            query=None,
            max_results=job.max_results,
            include_from_me=job.include_from_me,
            progress_cb=on_progress,
        )
    except Exception as e:
        job.error = str(e)
    finally:
        job.finished_at = datetime.utcnow().isoformat() + "Z"


@app.post("/api/gmail/fetch/start", response_class=HTMLResponse, name="api_gmail_fetch_start")
async def api_gmail_fetch_start(
    request: Request,
    label: str = Form("Support收件"),
    max_results: str = Form(""),
    include_from_me: bool = Form(False),
) -> HTMLResponse:
    label = (label or "").strip() or "Support收件"
    mr: Optional[int] = None
    if (max_results or "").strip():
        try:
            mr = int(max_results)
        except Exception:
            raise HTTPException(status_code=400, detail="max_results must be int")
        mr = max(1, min(mr, 50000))

    job_id = uuid.uuid4().hex
    job = FetchJob(job_id=job_id, label=label, max_results=mr, include_from_me=include_from_me)
    FETCH_JOBS[job_id] = job

    asyncio.create_task(_run_fetch(job))

    return templates.TemplateResponse("partials/fetch_status.html", {"request": request, "job": job})


@app.get("/api/gmail/fetch/status/{job_id}", response_class=HTMLResponse, name="api_gmail_fetch_status")
def api_gmail_fetch_status(request: Request, job_id: str) -> HTMLResponse:
    job = FETCH_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return templates.TemplateResponse("partials/fetch_status.html", {"request": request, "job": job})

