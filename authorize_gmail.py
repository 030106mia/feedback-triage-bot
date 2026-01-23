from __future__ import annotations

import os
import traceback
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

CREDENTIALS_PATH = "secrets/gmail_credentials.json"
TOKEN_PATH = "secrets/gmail_token.json"

def main():
    print("== Gmail OAuth (readonly) ==")

    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(f"Missing {CREDENTIALS_PATH}")

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)

    # 1) 优先本地回调（通常会自动打开浏览器）
    try:
        print("Starting local server auth (should open browser)...")
        creds = flow.run_local_server(
            host="localhost",
            port=0,
            prompt="consent",
            authorization_prompt_message="Please authorize Gmail access",
            open_browser=True,
        )
    except Exception:
        # 2) 如果本地回调失败，改用手动复制 URL
        print("Local server auth failed. Falling back to manual URL.")
        traceback.print_exc()

        auth_url, _ = flow.authorization_url(prompt="consent")
        print("\nOpen this URL in your browser:\n")
        print(auth_url)
        code = input("\nPaste the code here: ").strip()

        flow.fetch_token(code=code)
        creds = flow.credentials

    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    print(f"\n✅ Success. Token saved to {TOKEN_PATH}")

if __name__ == "__main__":
    main()
