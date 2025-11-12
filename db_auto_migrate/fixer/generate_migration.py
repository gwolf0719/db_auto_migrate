# 說明：本模組封裝 Alembic autogenerate 流程，當偵測到 schema 差異時自動建立新的遷移腳本。
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData


@dataclass(slots=True)
class AutogenerateResult:
    """自動產生遷移腳本的結果。"""

    created_revision: Optional[str]
    script_path: Optional[str]
    had_changes: bool


def autogenerate_revision(
    alembic_cfg: Config,
    metadata: Sequence[MetaData],
    message: str = "Auto generated migration",
    include_object: Optional[Callable[..., bool]] = None,
) -> AutogenerateResult:
    """使用 Alembic autogenerate 產生遷移腳本，若無差異則不產生檔案。"""

    if not metadata:
        raise ValueError("autogenerate_revision 需要至少一個 MetaData。")

    target_metadata = metadata[0] if len(metadata) == 1 else tuple(metadata)
    script_directory = ScriptDirectory.from_config(alembic_cfg)
    existing_heads = set(script_directory.get_heads())
    had_changes = False

    def process_revision_directives(context, revision, directives):
        nonlocal had_changes
        if not directives:
            return
        directive = directives[0]
        if directive.upgrade_ops.is_empty():
            directives[:] = []
            return
        had_changes = True

    alembic_cfg.attributes["process_revision_directives"] = process_revision_directives
    alembic_cfg.attributes["target_metadata"] = target_metadata
    alembic_cfg.attributes["compare_type"] = True
    alembic_cfg.attributes["compare_server_default"] = True
    alembic_cfg.attributes["include_object"] = include_object

    command.revision(alembic_cfg, message=message, autogenerate=True)
    refreshed = ScriptDirectory.from_config(alembic_cfg)
    new_heads = set(refreshed.get_heads())
    created_revisions = list(new_heads - existing_heads)

    if not had_changes and not created_revisions:
        return AutogenerateResult(created_revision=None, script_path=None, had_changes=False)

    had_changes = had_changes or bool(created_revisions)
    revision_id = created_revisions[0] if created_revisions else refreshed.get_current_head()
    revision = refreshed.get_revision(revision_id)

    return AutogenerateResult(
        created_revision=revision_id,
        script_path=str(revision.path),
        had_changes=had_changes,
    )

