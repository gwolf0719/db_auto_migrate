# 說明：本模組負責檢查多個資料庫環境之間的 Alembic 版本是否一致，協助發現環境差異。
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..config import DBEnvironment


@dataclass(slots=True)
class EnvironmentState:
    """描述單一環境的遷移狀態。"""

    name: str
    heads: List[str] = field(default_factory=list)


@dataclass(slots=True)
class EnvironmentConsistencyReport:
    """彙整多環境之間的差異。"""

    primary: EnvironmentState
    others: List[EnvironmentState] = field(default_factory=list)
    mismatched: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def is_consistent(self) -> bool:
        return not self.mismatched


class EnvironmentConsistencyChecker:
    """比對多個環境的 Alembic 版本狀態。"""

    def __init__(self, alembic_cfg: Config, environments: Sequence[DBEnvironment]) -> None:
        self.alembic_cfg = alembic_cfg
        self.environments = environments
        self._engines: Dict[str, Engine] = {}

    def check(self) -> EnvironmentConsistencyReport:
        primary_url = self.alembic_cfg.get_main_option("sqlalchemy.url")
        if not primary_url:
            raise ValueError("Alembic 設定缺少 sqlalchemy.url，無法執行環境比對。")

        primary_state = EnvironmentState(
            name="primary",
            heads=self._fetch_heads("primary", primary_url),
        )
        others: List[EnvironmentState] = []
        mismatched: Dict[str, List[str]] = {}

        for env in self.environments:
            env_state = EnvironmentState(name=env.name, heads=self._fetch_heads(env.name, env.database_url))
            others.append(env_state)
            if set(env_state.heads) != set(primary_state.heads):
                mismatched[env.name] = env_state.heads

        return EnvironmentConsistencyReport(primary=primary_state, others=others, mismatched=mismatched)

    def _fetch_heads(self, key: str, url: str) -> List[str]:
        engine = self._get_engine(key, url)
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                rows = result.fetchall()
                return [row[0] for row in rows]
        except (ProgrammingError, OperationalError):
            return []

    def _get_engine(self, key: str, url: str) -> Engine:
        if key not in self._engines:
            self._engines[key] = create_engine(url, future=True)
        return self._engines[key]

