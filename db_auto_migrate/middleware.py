# 說明：本模組提供 FastAPI 專用的 middleware，於應用第一個請求前自動觸發 init_db 進行資料庫檢查與修復。
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from .core import init_db


class DBAutoMigrateMiddleware(BaseHTTPMiddleware):
    """在應用層自動觸發資料庫遷移檢查與修復。"""

    def __init__(self, app, **init_kwargs: Any) -> None:
        super().__init__(app)
        self._init_kwargs = init_kwargs
        self._initialized = False
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    await init_db(**self._init_kwargs)
                    self._initialized = True
        response = await call_next(request)
        return response

