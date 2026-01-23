# fetch_test.py
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# 读取刚才 OAuth 生成的 token
creds = Credentials.from_authorized_user_file(
    "secrets/gmail_token.json",
    SCOPES
)

# 构建 Gmail API client
service = build("gmail", "v1", credentials=creds)

# 拉最近 5 封邮件（只拿 id）
results = service.users().messages().list(
    userId="me",
    maxResults=5
).execute()

messages = results.get("messages", [])

print("Fetched messages:")
for msg in messages:
    print(msg["id"])
