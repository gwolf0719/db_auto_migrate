# 說明：本模組負責檢測 Alembic 遷移腳本與資料庫版本間的衝突情況，例如多個 head、遺失的父節點與資料庫版本漂移。
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.script.revision import ResolutionError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError


@dataclass(slots=True)
class MissingLink:
    """記錄遺失的父節點資訊。"""

    revision: str
    missing_parent: str


@dataclass(slots=True)
class MigrationConflictReport:
    """整體衝突檢查結果。"""

    script_heads: List[str] = field(default_factory=list)
    database_heads: List[str] = field(default_factory=list)
    missing_links: List[MissingLink] = field(default_factory=list)
    detached_database_heads: List[str] = field(default_factory=list)

    @property
    def has_multiple_heads(self) -> bool:
        return len(self.script_heads) > 1

    @property
    def has_missing_links(self) -> bool:
        return bool(self.missing_links)

    @property
    def has_detached_heads(self) -> bool:
        return bool(self.detached_database_heads)

    @property
    def is_clean(self) -> bool:
        return (
            not self.has_multiple_heads
            and not self.has_missing_links
            and not self.has_detached_heads
        )


class MigrationConflictDetector:
    """檢測遷移腳本與資料庫間的衝突。"""

    def __init__(self, alembic_cfg: Config, database_url: Optional[str] = None) -> None:
        self.alembic_cfg = alembic_cfg
        self.database_url = database_url or alembic_cfg.get_main_option("sqlalchemy.url")
        self._engine: Optional[Engine] = None

    def detect(self) -> MigrationConflictReport:
        script_dir = ScriptDirectory.from_config(self.alembic_cfg)
        script_heads = list(script_dir.get_heads())

        missing_links = self._detect_missing_links(script_dir)
        database_heads = self._fetch_database_heads()
        detached_heads = [head for head in database_heads if head not in script_heads]

        return MigrationConflictReport(
            script_heads=script_heads,
            database_heads=database_heads,
            missing_links=missing_links,
            detached_database_heads=detached_heads,
        )

    def _detect_missing_links(self, script_dir: ScriptDirectory) -> List[MissingLink]:
        missing: List[MissingLink] = []
        for revision in script_dir.walk_revisions():
            down_revision = revision.down_revision
            if down_revision is None:
                continue
            parents: Sequence[str]
            if isinstance(down_revision, tuple):
                parents = down_revision
            else:
                parents = (down_revision,)
            for parent in parents:
                try:
                    script_dir.get_revision(parent)
                except ResolutionError:
                    missing.append(MissingLink(revision=revision.revision, missing_parent=parent))
        return missing

    def _fetch_database_heads(self) -> List[str]:
        if not self.database_url:
            return []
        engine = self._get_engine()
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                rows = result.fetchall()
                return [row[0] for row in rows]
        except (ProgrammingError, OperationalError):
            # 資料庫尚未初始化或版本表缺失
            return []

    def _get_engine(self) -> Engine:
        if self._engine is None:
            if not self.database_url:
                raise ValueError("未提供資料庫連線 URL，無法檢查資料庫版本。")
            self._engine = create_engine(self.database_url, future=True)
        return self._engine

