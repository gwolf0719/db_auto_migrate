# 說明：匯出自動修復與環境同步相關的工具函式，供核心流程使用。
from .auto_merge import AutoMergeResult, merge_heads
from .generate_migration import AutogenerateResult, autogenerate_revision
from .sync_env import SyncResult, upgrade_environment

__all__ = [
    "AutoMergeResult",
    "merge_heads",
    "AutogenerateResult",
    "autogenerate_revision",
    "SyncResult",
    "upgrade_environment",
]

