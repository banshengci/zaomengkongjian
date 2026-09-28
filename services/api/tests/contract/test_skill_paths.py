"""skill 路径与工具调用的轻量契约。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.integrate.skill_paths import SkillLayoutError, resolve_skill_paths


def test_resolve_skill_paths_finds_workspace_clone() -> None:
    paths = resolve_skill_paths()
    assert paths.root.exists()
    assert paths.build_prompt_payload.exists()
    assert paths.init_host_run.exists()
    assert (paths.root / "references" / "output_schema.md").exists()


def test_resolve_skill_paths_rejects_incomplete(tmp_path: Path) -> None:
    fake = tmp_path / "skill"
    fake.mkdir()
    with pytest.raises(SkillLayoutError):
        resolve_skill_paths(fake)
