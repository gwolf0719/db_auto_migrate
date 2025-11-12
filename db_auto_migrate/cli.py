# 說明：本模組提供命令列介面，方便透過 CLI 操作資料庫遷移檢查、修復與同步。
from __future__ import annotations

import asyncio
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from .config import DBEnvironment
from .core import InitDBResult, init_db

app = typer.Typer(help="db-auto-migrate CLI 工具")
console = Console()


def _parse_environments(envs: List[str]) -> List[DBEnvironment]:
    parsed: List[DBEnvironment] = []
    for item in envs:
        if "=" not in item:
            raise typer.BadParameter("環境參數格式需為 <name>=<database_url>")
        name, url = item.split("=", 1)
        parsed.append(DBEnvironment(name=name.strip(), database_url=url.strip()))
    return parsed


def _render_result(result: InitDBResult) -> None:
    table = Table(title="db-auto-migrate 檢查摘要")
    table.add_column("項目")
    table.add_column("狀態 / 詳細資訊")

    conflicts = result.conflict_report
    if conflicts.is_clean:
        table.add_row("遷移衝突", "無")
    else:
        details: List[str] = []
        if conflicts.has_multiple_heads:
            details.append(f"多個 head: {', '.join(conflicts.script_heads)}")
        if conflicts.has_missing_links:
            missing = ", ".join(f"{link.revision}->{link.missing_parent}" for link in conflicts.missing_links)
            details.append(f"遺失父節點: {missing}")
        if conflicts.has_detached_heads:
            details.append(f"資料庫未追蹤 head: {', '.join(conflicts.detached_database_heads)}")
        table.add_row("遷移衝突", "; ".join(details))

    if result.schema_diff_report:
        if result.schema_diff_report.has_changes:
            diff_preview = "\n".join(result.schema_diff_report.operations[:5])
            table.add_row("Schema 差異", diff_preview or "有差異")
        else:
            table.add_row("Schema 差異", "無")
    else:
        table.add_row("Schema 差異", "未執行比對（缺少 MetaData）")

    if result.environment_report:
        if result.environment_report.is_consistent:
            table.add_row("多環境狀態", "一致")
        else:
            mismatch = ", ".join(
                f"{name}: {', '.join(heads)}"
                for name, heads in result.environment_report.mismatched.items()
            )
            table.add_row("多環境狀態", f"不一致 -> {mismatch}")
    console.print(table)

    if result.auto_merge_result:
        console.print(
            f"[green]已自動合併 head：{result.auto_merge_result.merged_heads} -> {result.auto_merge_result.created_revision}[/]"
        )
    if result.autogenerate_result and result.autogenerate_result.had_changes:
        console.print(
            f"[green]已自動產出遷移檔：{result.autogenerate_result.created_revision} ({result.autogenerate_result.script_path})[/]"
        )
    if result.environment_sync_results:
        for sync in result.environment_sync_results:
            console.print(f"[green]環境 {sync.environment} 已升級到 {sync.target_revision}[/]")


def _run_init_db(
    alembic_ini_path: str,
    metadata_modules: List[str],
    environments: List[DBEnvironment],
    auto_fix: bool,
    auto_merge_heads: bool,
    auto_generate: bool,
    auto_upgrade: bool,
) -> InitDBResult:
    return asyncio.run(
        init_db(
            alembic_ini_path=alembic_ini_path,
            metadata_modules=metadata_modules,
            environments=environments,
            auto_fix=auto_fix,
            auto_merge_heads=auto_merge_heads,
            auto_generate=auto_generate,
            auto_upgrade=auto_upgrade,
        )
    )


@app.command()
def check(
    alembic_ini: str = typer.Option("alembic.ini", "--ini", help="Alembic 設定檔路徑"),
    metadata_module: List[str] = typer.Option(
        [], "--metadata", "-m", help="包含 SQLAlchemy MetaData 的模組路徑（module:attr）"
    ),
    env: List[str] = typer.Option([], "--env", help="額外環境定義，格式為 name=url"),
) -> None:
    """僅檢查資料庫狀態，不進行修復。"""

    environments = _parse_environments(env)
    result = _run_init_db(
        alembic_ini_path=alembic_ini,
        metadata_modules=metadata_module,
        environments=environments,
        auto_fix=False,
        auto_merge_heads=False,
        auto_generate=False,
        auto_upgrade=False,
    )
    _render_result(result)
    if not result.conflict_report.is_clean or (
        result.schema_diff_report and result.schema_diff_report.has_changes
    ):
        raise typer.Exit(code=1)


@app.command()
def fix(
    alembic_ini: str = typer.Option("alembic.ini", "--ini", help="Alembic 設定檔路徑"),
    metadata_module: List[str] = typer.Option(
        [], "--metadata", "-m", help="包含 SQLAlchemy MetaData 的模組路徑（module:attr）"
    ),
    env: List[str] = typer.Option([], "--env", help="額外環境定義，格式為 name=url"),
) -> None:
    """檢查並自動修復遷移衝突與 schema 差異。"""

    environments = _parse_environments(env)
    result = _run_init_db(
        alembic_ini_path=alembic_ini,
        metadata_modules=metadata_module,
        environments=environments,
        auto_fix=True,
        auto_merge_heads=True,
        auto_generate=True,
        auto_upgrade=True,
    )
    _render_result(result)


@app.command()
def sync(
    alembic_ini: str = typer.Option("alembic.ini", "--ini", help="Alembic 設定檔路徑"),
    env: List[str] = typer.Option([], "--env", help="欲同步的環境，格式為 name=url"),
    metadata_module: List[str] = typer.Option([], "--metadata", "-m", help="MetaData 模組"),
) -> None:
    """將指定環境升級到最新 head。"""

    environments = _parse_environments(env)
    if not environments:
        raise typer.BadParameter("同步至少需要指定一個環境，例如 --env staging=postgresql://...")
    result = _run_init_db(
        alembic_ini_path=alembic_ini,
        metadata_modules=metadata_module,
        environments=environments,
        auto_fix=True,
        auto_merge_heads=True,
        auto_generate=False,
        auto_upgrade=True,
    )
    _render_result(result)


@app.command()
def autogen(
    alembic_ini: str = typer.Option("alembic.ini", "--ini", help="Alembic 設定檔路徑"),
    metadata_module: List[str] = typer.Option(
        [], "--metadata", "-m", help="包含 SQLAlchemy MetaData 的模組路徑（module:attr）"
    ),
) -> None:
    """只執行 autogenerate 建立遷移檔並升級資料庫。"""

    result = _run_init_db(
        alembic_ini_path=alembic_ini,
        metadata_modules=metadata_module,
        environments=[],
        auto_fix=True,
        auto_merge_heads=False,
        auto_generate=True,
        auto_upgrade=True,
    )
    _render_result(result)


if __name__ == "__main__":
    app()

