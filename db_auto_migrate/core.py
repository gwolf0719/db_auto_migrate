# 說明：本模組實作 init_db 核心流程，整合偵測、修復與多環境同步邏輯，於 FastAPI 啟動時自動驗證資料庫遷移狀態。
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Callable, Iterable, List, Optional, Sequence

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData

from .config import AutoFixSettings, DBEnvironment, LoadedConfig, PackageSettings, build_loaded_config
from .detector.env_consistency import EnvironmentConsistencyChecker, EnvironmentConsistencyReport
from .detector.migration_conflict import MigrationConflictDetector, MigrationConflictReport
from .detector.schema_diff import SchemaDiffDetector, SchemaDiffReport
from .fixer.auto_merge import AutoMergeResult, merge_heads
from .fixer.generate_migration import AutogenerateResult, autogenerate_revision
from .fixer.sync_env import SyncResult, upgrade_environment


@dataclass(slots=True)
class InitDBResult:
    """彙整 init_db 的執行結果。"""

    conflict_report: MigrationConflictReport
    schema_diff_report: Optional[SchemaDiffReport]
    environment_report: Optional[EnvironmentConsistencyReport]
    auto_merge_result: Optional[AutoMergeResult] = None
    autogenerate_result: Optional[AutogenerateResult] = None
    environment_sync_results: List[SyncResult] = field(default_factory=list)


async def init_db(
    alembic_ini_path: str = "alembic.ini",
    script_location: Optional[str] = None,
    database_url: Optional[str] = None,
    metadata_modules: Optional[Sequence[str]] = None,
    metadata: Optional[Sequence[MetaData]] = None,
    environments: Optional[Sequence[DBEnvironment]] = None,
    auto_fix: bool = True,
    auto_merge_heads: bool = True,
    auto_generate: bool = True,
    auto_upgrade: bool = True,
    include_object: Optional[Callable[..., bool]] = None,
) -> InitDBResult:
    """
    FastAPI 啟動時呼叫的主要入口，會自動檢查並修復資料庫遷移問題。
    """

    auto_fix_settings = AutoFixSettings(
        auto_merge_heads=auto_merge_heads,
        auto_generate=auto_generate,
        auto_upgrade=auto_upgrade,
    )

    package_settings = PackageSettings(
        alembic_ini_path=alembic_ini_path,
        script_location=script_location,
        database_url=database_url,
        metadata_modules=list(metadata_modules or []),
        environments=list(environments or []),
        auto_fix=auto_fix_settings,
    )
    loaded_config = build_loaded_config(package_settings)
    if metadata:
        loaded_config.metadata = list(metadata)
    if not loaded_config.metadata and not metadata_modules:
        raise ValueError("init_db 需要提供 metadata_modules 或 metadata 以進行 schema 比對。")

    return await asyncio.to_thread(
        _init_db_sync,
        loaded_config,
        include_object,
        auto_fix,
    )


def _init_db_sync(
    loaded_config: LoadedConfig,
    include_object: Optional[Callable[..., bool]],
    auto_fix_enabled: bool,
) -> InitDBResult:
    alembic_cfg = Config(str(loaded_config.alembic_ini_path))
    if loaded_config.script_location:
        alembic_cfg.set_main_option("script_location", str(loaded_config.script_location))
    if loaded_config.database_url:
        alembic_cfg.set_main_option("sqlalchemy.url", loaded_config.database_url)

    conflict_detector = MigrationConflictDetector(alembic_cfg, loaded_config.database_url)
    conflict_report = conflict_detector.detect()

    schema_diff_report: Optional[SchemaDiffReport] = None
    if loaded_config.metadata:
        schema_diff_report = SchemaDiffDetector(
            alembic_cfg,
            loaded_config.metadata,
            include_object=include_object,
        ).detect()

    environment_report: Optional[EnvironmentConsistencyReport] = None
    if loaded_config.environments:
        environment_report = EnvironmentConsistencyChecker(
            alembic_cfg, loaded_config.environments
        ).check()

    auto_merge_result: Optional[AutoMergeResult] = None
    autogenerate_result: Optional[AutogenerateResult] = None
    environment_sync_results: List[SyncResult] = []

    if auto_fix_enabled:
        if conflict_report.has_multiple_heads and loaded_config.auto_fix.auto_merge_heads:
            auto_merge_result = merge_heads(alembic_cfg)

        if schema_diff_report and schema_diff_report.has_changes and loaded_config.auto_fix.auto_generate:
            autogenerate_result = autogenerate_revision(
                alembic_cfg,
                loaded_config.metadata,
            )
            if (
                autogenerate_result
                and autogenerate_result.had_changes
                and loaded_config.auto_fix.auto_upgrade
            ):
                command.upgrade(alembic_cfg, "head")

        if environment_report and not environment_report.is_consistent:
            for env in loaded_config.environments:
                if environment_report.mismatched.get(env.name) is not None:
                    sync_result = upgrade_environment(alembic_cfg, env, "head")
                    environment_sync_results.append(sync_result)

    return InitDBResult(
        conflict_report=conflict_report,
        schema_diff_report=schema_diff_report,
        environment_report=environment_report,
        auto_merge_result=auto_merge_result,
        autogenerate_result=autogenerate_result,
        environment_sync_results=environment_sync_results,
    )

