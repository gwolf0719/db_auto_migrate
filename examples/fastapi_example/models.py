# 說明：此模組定義範例專案的 SQLAlchemy 模型與 MetaData，供 db_auto_migrate 示範使用。
from __future__ import annotations

from sqlalchemy import Column, Integer, MetaData, String, Table

metadata = MetaData()

user_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(length=255), nullable=False, unique=True),
)

