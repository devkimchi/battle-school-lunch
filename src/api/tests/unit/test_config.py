from pathlib import Path

import pytest

from app.config import _find_env_file


@pytest.mark.unit
def test_find_env_file_locates_ancestor_file(tmp_path: Path) -> None:
    project = tmp_path / "project"
    app_dir = project / "src" / "api" / "app"
    app_dir.mkdir(parents=True)
    env_file = project / ".env"
    env_file.touch()

    assert _find_env_file(app_dir) == env_file


@pytest.mark.unit
def test_find_env_file_handles_shallow_path(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()

    assert _find_env_file(app_dir) is None
