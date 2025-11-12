# 說明：本模組負責讀取並組態 db_auto_migrate 套件所需的設定，包含 Alembic 路徑、資料庫連線與自動修復選項。
from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from pydantic import BaseModel, Field
from sqlalchemy import MetaData


class AutoFixSettings(BaseModel):
    """自動修復相關的細部設定。"""

    auto_merge_heads: bool = True
    auto_generate: bool = True
    auto_upgrade: bool = True
    interactive_on_production: bool = True
    production_envs: List[str] = Field(default_factory=list)


class DBEnvironment(BaseModel):
    """代表一個額外需要檢查的資料庫環境。"""

    name: str
    database_url: str


class PackageSettings(BaseModel):
    """套件的主設定。"""

    alembic_ini_path: str = "alembic.ini"
    script_location: Optional[str] = None
    database_url: Optional[str] = None
    metadata_modules: List[str] = Field(default_factory=list)
    environments: List[DBEnvironment] = Field(default_factory=list)
    auto_fix: AutoFixSettings = Field(default_factory=AutoFixSettings)


@dataclass(slots=True)
class LoadedConfig:
    """整合後可供核心流程使用的設定。"""

    alembic_ini_path: Path
    script_location: Optional[Path]
    database_url: Optional[str]
    metadata: List[MetaData] = field(default_factory=list)
    environments: List[DBEnvironment] = field(default_factory=list)
    auto_fix: AutoFixSettings = field(default_factory=AutoFixSettings)

    def ensure_metadata(self) -> None:
        if not self.metadata:
            raise ValueError("未載入任何 SQLAlchemy MetaData，無法執行 schema 比對。")


def load_metadata_from_modules(modules: Sequence[str]) -> List[MetaData]:
    """根據模組路徑載入 MetaData 物件。"""

    metadata_objects: List[MetaData] = []
    for dotted_path in modules:
        module_path, _, attr = dotted_path.partition(":")
        module = import_module(module_path)
        if attr:
            candidate = getattr(module, attr)
        else:
            candidate = getattr(module, "metadata", None)
        if candidate is None:
            raise AttributeError(f"模組 {module_path} 不包含可用的 MetaData：{attr or 'metadata'}")
        if isinstance(candidate, Iterable):
            for item in candidate:
                if isinstance(item, MetaData):
                    metadata_objects.append(item)
        elif isinstance(candidate, MetaData):
            metadata_objects.append(candidate)
        else:
            raise TypeError(f"{dotted_path} 不是合法的 MetaData 物件")
    return metadata_objects


def build_loaded_config(settings: PackageSettings) -> LoadedConfig:
    """將 Pydantic 設定轉換為核心流程可用的結構。"""

    ini_path = Path(settings.alembic_ini_path).resolve()
    script_path = (
        Path(settings.script_location).resolve() if settings.script_location else None
    )
    metadata = load_metadata_from_modules(settings.metadata_modules)

    return LoadedConfig(
        alembic_ini_path=ini_path,
        script_location=script_path,
        database_url=settings.database_url,
        metadata=metadata,
        environments=settings.environments,
        auto_fix=settings.auto_fix,
    )

