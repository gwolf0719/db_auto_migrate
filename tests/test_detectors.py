# 說明：本測試涵蓋遷移衝突與多環境檢查等偵測模組的基本行為。
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from db_auto_migrate.detector.env_consistency import EnvironmentConsistencyChecker
from db_auto_migrate.detector.migration_conflict import MigrationConflictDetector
from db_auto_migrate.config import DBEnvironment


def test_migration_conflict_detector_reports_multiple_heads(alembic_workspace) -> None:
    config, metadata, engine = alembic_workspace

    versions_path = Path(config.get_main_option("script_location")) / "versions"
    (versions_path / "rev_a.py").write_text(
        "\n".join(
            [
                "# 說明：測試用遷移檔 rev_a。",
                "revision = 'rev_a'",
                "down_revision = None",
                "branch_labels = None",
                "depends_on = None",
                "",
                "def upgrade():",
                "    pass",
                "",
                "def downgrade():",
                "    pass",
            ]
        ),
        encoding="utf-8",
    )
    (versions_path / "rev_b.py").write_text(
        "\n".join(
            [
                "# 說明：測試用遷移檔 rev_b。",
                "revision = 'rev_b'",
                "down_revision = None",
                "branch_labels = None",
                "depends_on = None",
                "",
                "def upgrade():",
                "    pass",
                "",
                "def downgrade():",
                "    pass",
            ]
        ),
        encoding="utf-8",
    )

    detector = MigrationConflictDetector(config)
    report = detector.detect()
    assert report.has_multiple_heads
    assert set(report.script_heads) == {"rev_a", "rev_b"}


def test_environment_consistency_checker_detects_mismatch(alembic_workspace) -> None:
    config, metadata, engine = alembic_workspace

    staging_path = Path(config.get_main_option("script_location")).parent / "staging.db"
    staging_url = f"sqlite:///{staging_path}"
    with create_engine(staging_url, future=True).begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:version)"), {"version": "fake_head"})

    other_env = DBEnvironment(name="staging", database_url=staging_url)
    checker = EnvironmentConsistencyChecker(config, [other_env])
    report = checker.check()

    assert not report.is_consistent
    assert "staging" in report.mismatched

