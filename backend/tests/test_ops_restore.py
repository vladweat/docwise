import hashlib
import os
import shutil
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


@pytest.mark.parametrize("keep_on_failure", [False, True], ids=["cleanup", "preserve-explicitly"])
def test_restore_drill_handles_mid_restore_failure_in_only_temporary_project(
    tmp_path, keep_on_failure
):
    root = Path(__file__).resolve().parents[2]
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    real_bash = shutil.which("bash")
    assert real_bash is not None

    fake_bash = fake_bin / "bash"
    fake_bash.write_text(
        f"#!{real_bash}\n"
        "set -euo pipefail\n"
        "script=\"$1\"; shift\n"
        "case \"$script\" in\n"
        "  ops/backup-pilot.sh)\n"
        "    mkdir -p \"$1/minio\"\n"
        "    touch \"$1/postgres.dump\"\n"
        "    exit 0\n"
        "    ;;\n"
        "  ops/restore-pilot.sh)\n"
        "    docker compose up -d postgres\n"
        "    exit 42\n"
        "    ;;\n"
        "  *) exit 99 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_bash.chmod(0o755)

    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        f"#!{real_bash}\n"
        "set -euo pipefail\n"
        "case \"$1\" in\n"
        "  ps|volume|network) exit 0 ;;\n"
        "  compose)\n"
        "    printf '%s|%s\\n' \"$COMPOSE_PROJECT_NAME\" \"$*\" >> \"$DOCKER_CALL_LOG\"\n"
        "    if [[ \"$2\" == up ]]; then touch \"$DRILL_RESOURCE_MARKER\"; fi\n"
        "    if [[ \"$2\" == down ]]; then rm -f \"$DRILL_RESOURCE_MARKER\"; fi\n"
        "    exit 0\n"
        "    ;;\n"
        "  *) exit 98 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    source_project = f"source-{uuid4().hex}"
    drill_project = f"docwise-restore-drill-{uuid4().hex}"
    backup_dir = tmp_path / "backup"
    docker_call_log = tmp_path / "docker-calls.txt"
    resource_marker = tmp_path / "drill-resource-created"
    env = os.environ.copy()
    env.update(
        {
            "RESTORE_DRILL_CONFIRM": "YES",
            "RESTORE_DRILL_SOURCE_PROJECT": source_project,
            "RESTORE_DRILL_PROJECT": drill_project,
            "RESTORE_DRILL_BACKUP_DIR": str(backup_dir),
            "RESTORE_DRILL_KEEP_ON_FAILURE": "1" if keep_on_failure else "0",
            "DOCKER_CALL_LOG": str(docker_call_log),
            "DRILL_RESOURCE_MARKER": str(resource_marker),
            "COMPOSE_PROJECT_NAME": source_project,
            "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
        }
    )

    result = subprocess.run(
        [real_bash, str(root / "ops/restore-drill.sh")],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 42
    calls = docker_call_log.read_text(encoding="utf-8").splitlines()
    expected_up = f"{drill_project}|compose up -d postgres"
    assert calls[0] == expected_up
    assert source_project not in "\n".join(calls)
    if keep_on_failure:
        assert calls == [expected_up]
        assert resource_marker.exists()
        assert "preserving failed drill project" in result.stdout
    else:
        assert calls == [expected_up, f"{drill_project}|compose down --volumes --remove-orphans"]
        assert not resource_marker.exists()
