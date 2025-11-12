# 說明：本模組提供對外匯出的主要 API，包括 init_db、middleware 與 CLI 入口。
from .core import init_db
from .middleware import DBAutoMigrateMiddleware

__all__ = ["init_db", "DBAutoMigrateMiddleware"]

