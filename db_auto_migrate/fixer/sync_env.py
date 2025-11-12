# 說明：本模組負責在多環境間同步 Alembic 遷移版本，透過自動升級指定環境到最新 head。
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from alembic import command
from alembic.config import Config

from ..config import DBEnvironment


@dataclass(slots=True)
class SyncResult:
    """環境同步的結果摘要。"""

    environment: str
    target_revision: str


def upgrade_environment(
    alembic_cfg: Config,
    environment: DBEnvironment,
    target_revision: str = "head",
) -> SyncResult:
    """將指定環境的資料庫升級到目標版本。"""

    original_url: Optional[str] = alembic_cfg.get_main_option("sqlalchemy.url")
    try:
        alembic_cfg.set_main_option("sqlalchemy.url", environment.database_url)
        command.upgrade(alembic_cfg, target_revision)
    finally:
        if original_url:
            alembic_cfg.set_main_option("sqlalchemy.url", original_url)
    return SyncResult(environment=environment.name, target_revision=target_revision)

