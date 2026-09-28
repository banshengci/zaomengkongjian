"""解析造梦 skill 安装路径并校验布局。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings

REQUIRED_RELATIVE = (
    "tools/init_host_run.py",
    "tools/build_prompt_payload.py",
    "tools/materialize_persona_bundle.py",
    "tools/export_relation_graph.py",
    "tools/verify_host_workflow.py",
    "references/output_schema.md",
)


class SkillLayoutError(RuntimeError):
    """zaomeng-skill 目录不完整。"""


@dataclass(frozen=True, slots=True)
class SkillPaths:
    root: Path
    tools: Path

    @property
    def init_host_run(self) -> Path:
        return self.tools / "init_host_run.py"

    @property
    def build_prompt_payload(self) -> Path:
        return self.tools / "build_prompt_payload.py"

    @property
    def materialize_persona_bundle(self) -> Path:
        return self.tools / "materialize_persona_bundle.py"

    @property
    def export_relation_graph(self) -> Path:
        return self.tools / "export_relation_graph.py"

    @property
    def verify_host_workflow(self) -> Path:
        return self.tools / "verify_host_workflow.py"


def resolve_skill_paths(root: Path | None = None) -> SkillPaths:
    """解析 skill 根目录；允许相对路径，相对 CWD 或配置里的根。"""
    settings = get_settings()
    base = Path(root or settings.zaomeng_skill_root)
    if not base.is_absolute():
        # 优先相对 services/api 的工程根，再相对 CWD
        candidates = [
            Path.cwd() / base,
            Path(__file__).resolve().parents[4] / base,
            Path(__file__).resolve().parents[3].parent.parent / base,
        ]
        for candidate in candidates:
            if candidate.exists():
                base = candidate
                break
    base = base.resolve()
    missing = [rel for rel in REQUIRED_RELATIVE if not (base / rel).exists()]
    if missing:
        raise SkillLayoutError(
            f"zaomeng-skill layout incomplete under {base}: missing {', '.join(missing)}"
        )
    return SkillPaths(root=base, tools=base / "tools")
