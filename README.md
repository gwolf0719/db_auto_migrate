<!-- 說明：本文件提供 db_auto_migrate 套件的使用方式、功能概述與開發流程注意事項。 -->
# db_auto_migrate

`db_auto_migrate` 是一個專為 FastAPI 與 Alembic 設計的自動化資料庫遷移管理套件，協助多開發者、多環境專案確保資料庫 schema 隨時同步且自動修復常見問題。

## 功能特色

- 啟動 FastAPI 時自動呼叫 `init_db()`，驗證資料庫與遷移狀態。
- 自動偵測並合併 Alembic 多 head 與缺失的 revision。
- 透過 autogenerate 機制偵測 models 變更並自動產生遷移腳本，隨即升級資料庫。
- 比對多環境（如 dev/staging/prod）資料庫狀態並提供同步機制。
- 提供 CLI 與 FastAPI middleware，方便以程式或命令列操作。

## 安裝方式

```bash
pip install git+https://github.com/<your-org-or-user>/db_auto_migrate.git
```

或在開發中使用 Poetry：

```bash
poetry add git+https://github.com/<your-org-or-user>/db_auto_migrate.git
```

## 基本使用

```python
from fastapi import FastAPI
from db_auto_migrate import init_db

app = FastAPI()

@app.on_event("startup")
async def startup() -> None:
    await init_db(
        alembic_ini_path="alembic.ini",
        auto_fix=True,
        check_envs=["dev", "staging"],
    )
```

## CLI 範例

```bash
db-auto-migrate check --config alembic.ini
db-auto-migrate fix --auto-merge
db-auto-migrate sync --from dev --to staging
db-auto-migrate autogen
```

## 開發流程

1. 安裝依賴：`poetry install`
2. 啟動測試：`poetry run pytest`
3. 程式碼風格：`poetry run black .` 與 `poetry run ruff .`
4. 型別檢查：`poetry run mypy .`

## 授權

MIT License

