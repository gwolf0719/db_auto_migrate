# 說明：本測試設定檔建立臨時 Alembic 環境與 SQLite 資料庫，供各項功能測試共用。
from __future__ import annotations

from pathlib import Path
import sys
import textwrap
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Iterator, Tuple

import pytest
from alembic.config import Config
from sqlalchemy import Column, Integer, MetaData, Table, create_engine
from sqlalchemy.engine import Engine


@pytest.fixture()
def alembic_workspace(tmp_path: Path) -> Iterator[Tuple[Config, MetaData, Engine]]:
    """建立臨時 Alembic 環境並提供 Config、MetaData 與 Engine。"""

    database_path = tmp_path / "app.db"
    database_url = f"sqlite:///{database_path}"
    script_location = tmp_path / "migrations"
    versions_path = script_location / "versions"
    versions_path.mkdir(parents=True)

    env_py = script_location / "env.py"
    env_py.write_text(
        textwrap.dedent(
            """\
# 說明：Alembic 測試環境設定，支援 autogenerate 與同步。
from __future__ import annotations

import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = config.attributes.get("target_metadata")


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""
        ),
        encoding="utf-8",
    )
    (script_location / "script.py.mako").write_text(
        textwrap.dedent(
            """\
# 說明：Alembic 測試環境使用的遷移檔模板。
\"\"\"${message}\"\"\"
revision = '${up_revision}'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
${upgrades if upgrades else "    pass"}


def downgrade() -> None:
${downgrades if downgrades else "    pass"}
"""
        ),
        encoding="utf-8",
    )

    ini_path = tmp_path / "alembic.ini"
    ini_path.write_text(
        textwrap.dedent(
            f"""\
# 說明：測試環境使用的 Alembic 設定檔。
[alembic]
script_location = {script_location}
sqlalchemy.url = {database_url}

[loggers]
keys = root

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[handler_console]
class = StreamHandler
args = (sys.stdout,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)s %(name)s %(message)s
"""
        ),
        encoding="utf-8",
    )

    config = Config(str(ini_path))
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", database_url)

    metadata = MetaData()
    Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
    )

    engine = create_engine(database_url, future=True)
    metadata.create_all(engine)

    yield config, metadata, engine

    engine.dispose()

