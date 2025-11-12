# 說明：本模組透過 Alembic autogenerate 機制比對 SQLAlchemy Models 與實際資料庫 schema，提供變更摘要以便後續自動產生遷移。
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

from alembic.autogenerate.api import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Connection


@dataclass(slots=True)
class SchemaDiffReport:
    """記錄 schema 差異的摘要資訊。"""

    has_changes: bool = False
    operations: List[str] = field(default_factory=list)


class SchemaDiffDetector:
    """利用 Alembic autogenerate 比對模型與資料庫差異。"""

    def __init__(
        self,
        alembic_cfg: Config,
        metadata: Sequence[MetaData],
        include_object: Optional[Callable[..., bool]] = None,
    ) -> None:
        if not metadata:
            raise ValueError("SchemaDiffDetector 需要至少一個 MetaData 來比較。")
        self.alembic_cfg = alembic_cfg
        self.metadata = metadata
        self.include_object = include_object

    def detect(self) -> SchemaDiffReport:
        database_url = self.alembic_cfg.get_main_option("sqlalchemy.url")
        if not database_url:
            raise ValueError("Alembic 設定中缺少 sqlalchemy.url，無法進行 schema 比對。")

        engine = create_engine(database_url, future=True)
        operations: List[str] = []

        if len(self.metadata) == 1:
            target_metadata: MetaData | Tuple[MetaData, ...] = self.metadata[0]
        else:
            target_metadata = tuple(self.metadata)

        with engine.connect() as connection:
            operations = self._collect_diffs(connection, target_metadata)

        return SchemaDiffReport(has_changes=bool(operations), operations=operations)

    def _collect_diffs(
        self,
        connection: Connection,
        target_metadata: MetaData | Tuple[MetaData, ...],
    ) -> List[str]:
        context = MigrationContext.configure(
            connection,
            opts={
                "compare_type": True,
                "compare_server_default": True,
                "include_object": self.include_object,
                "target_metadata": target_metadata,
            },
        )
        diffs = compare_metadata(context, target_metadata)
        return [self._render_diff(diff) for diff in diffs]

    def _render_diff(self, diff: Tuple[object, ...]) -> str:
        return str(diff)

