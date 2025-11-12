# 說明：本模組提供自動合併多個 Alembic head 的能力，以解決遷移分支衝突。
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


@dataclass(slots=True)
class AutoMergeResult:
    """自動合併操作的結果摘要。"""

    created_revision: Optional[str]
    merged_heads: List[str]


def merge_heads(alembic_cfg: Config, message: str = "Auto merge heads") -> Optional[AutoMergeResult]:
    """合併多個 head，若無需合併則回傳 None。"""

    script_dir = ScriptDirectory.from_config(alembic_cfg)
    heads = list(script_dir.get_heads())
    if len(heads) <= 1:
        return None

    command.merge(alembic_cfg, revisions=heads, message=message)

    refreshed = ScriptDirectory.from_config(alembic_cfg)
    new_head = refreshed.get_current_head()

    return AutoMergeResult(created_revision=new_head, merged_heads=heads)

