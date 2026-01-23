from __future__ import annotations

# Vercel Serverless entrypoint.
# Vercel 会识别 FastAPI ASGI app 变量名 `app`

from web.server import app  # noqa: F401

