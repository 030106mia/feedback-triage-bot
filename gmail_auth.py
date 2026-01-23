from __future__ import annotations

import os
from typing import Optional

from google_auth_oauthlib.flow import Flow, InstalledAppFlow


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_PATH = "secrets/gmail_credentials.json"
TOKEN_PATH = "secrets/gmail_token.json"


class GmailAuthError(RuntimeError):
    pass


def token_exists() -> bool:
    return os.path.exists(TOKEN_PATH)


def credentials_exist() -> bool:
    return os.path.exists(CREDENTIALS_PATH)


def delete_token() -> None:
    if os.path.exists(TOKEN_PATH):
        os.remove(TOKEN_PATH)


def build_flow_for_web(redirect_uri: str, state: Optional[str] = None) -> Flow:
    if not credentials_exist():
        raise GmailAuthError(f"Missing {CREDENTIALS_PATH}")
    flow = Flow.from_client_secrets_file(CREDENTIALS_PATH, scopes=SCOPES, state=state)
    flow.redirect_uri = redirect_uri
    return flow


def authorization_url(flow: Flow) -> str:
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url


def exchange_code_and_save_token(flow: Flow, code: str) -> None:
    flow.fetch_token(code=code)
    creds = flow.credentials
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        f.write(creds.to_json())

