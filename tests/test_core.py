# 說明：本測試驗證 init_db 核心流程能自動產生遷移檔並回報摘要。
from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import Column, Integer, MetaData, String, Table

from db_auto_migrate.core import init_db


def test_init_db_autogenerate_creates_revision(alembic_workspace) -> None:
    config, metadata, engine = alembic_workspace

    upgraded_metadata = MetaData()
    Table(
        "users",
        upgraded_metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("email", String(length=255), nullable=False, server_default="test@example.com"),
    )

    result = asyncio.run(
        init_db(
            alembic_ini_path=str(Path(config.config_file_name)),
            metadata=[upgraded_metadata],
            auto_fix=True,
            auto_merge_heads=False,
            auto_generate=True,
            auto_upgrade=False,
        )
    )

    assert result.schema_diff_report is not None
    assert result.schema_diff_report.has_changes
    assert result.autogenerate_result is not None
    assert result.autogenerate_result.had_changes

    versions_path = Path(config.get_main_option("script_location")) / "versions"
    generated_files = list(versions_path.glob("*.py"))
    assert generated_files, "預期應產生至少一個遷移檔案"

