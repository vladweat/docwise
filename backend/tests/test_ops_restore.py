import hashlib
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.mark.parametrize(
    ("project_kind", "options", "include_backup_project", "expected_failure"),
    [
        ("normal", [], True, "project-mismatch"),
        ("drill", ["--wipe-volumes", "--allow-project-mismatch"], True, "later-validation"),
        ("normal", ["--wipe-volumes", "--allow-project-mismatch"], True, "project-mismatch"),
        ("drill", ["--allow-project-mismatch"], True, "project-mismatch"),
        ("normal", [], False, "missing-project"),
    ],
    ids=["normal-restore", "isolated-drill", "flag-is-not-enough", "wipe-is-required", "legacy-manifest"],
)
def test_restore_checks_compose_project_before_running_docker(
    tmp_path, project_kind, options, include_backup_project, expected_failure
):
    root = Path(__file__).resolve().parents[2]
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    (backup_dir / "postgres.dump").write_bytes(b"synthetic backup")
    (backup_dir / "minio").mkdir()
    backup_project = f"backup-{uuid4().hex}"
    current_project = (
        f"docwise-restore-drill-{uuid4().hex}"
        if project_kind == "drill"
        else f"current-{uuid4().hex}"
    )
    manifest = (
        "created_utc=2026-11-06T00:00:00Z\n"
        "alembic_revision=test-revision\n"
        + (f"compose_project={backup_project}\n" if include_backup_project else "")
    )
    (backup_dir / "manifest.txt").write_text(manifest, encoding="utf-8")
    checksums = []
    for filename in ("postgres.dump", "manifest.txt"):
        digest = hashlib.sha256((backup_dir / filename).read_bytes()).hexdigest()
        checksums.append(f"{digest}  {filename}\n")
    (backup_dir / "checksums.sha256").write_text("".join(checksums), encoding="utf-8")

    docker_marker = tmp_path / "docker-was-called"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        "#!/bin/sh\nprintf called > \"$DOCKER_CALL_MARKER\"\nexit 1\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    env = os.environ.copy()
    env["COMPOSE_PROJECT_NAME"] = current_project
    env["DOCKER_CALL_MARKER"] = str(docker_marker)
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    command = ["bash", str(root / "ops/restore-pilot.sh"), str(backup_dir)]
    command.extend(options)
    result = subprocess.run(
        command,
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    if expected_failure == "later-validation":
        assert "belongs to Compose project" not in result.stderr
        assert "unknown argument" not in result.stderr
    elif expected_failure == "missing-project":
        assert "no Compose project" in result.stderr
    elif expected_failure == "project-mismatch":
        assert "refusing restore" in result.stderr
        assert backup_project in result.stderr
        assert current_project in result.stderr
    else:
        raise AssertionError(f"unexpected expectation: {expected_failure}")
    assert not docker_marker.exists()
