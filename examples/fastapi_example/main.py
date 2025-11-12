# 說明：此範例示範如何在 FastAPI 專案中使用 db_auto_migrate 於啟動時自動初始化資料庫。
from __future__ import annotations

from fastapi import FastAPI

from db_auto_migrate import init_db

app = FastAPI(title="db-auto-migrate 範例")


@app.on_event("startup")
async def startup_event() -> None:
    await init_db(
        alembic_ini_path="alembic.ini",
        metadata_modules=["examples.fastapi_example.models:metadata"],
    )


@app.get("/")
async def read_root() -> dict[str, str]:
    return {"message": "db-auto-migrate ready"}

