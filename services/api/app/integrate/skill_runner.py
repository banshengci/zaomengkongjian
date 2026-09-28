"""通过子进程调用造梦 skill CLI 工具。

统一出口：路径解析、超时、stderr 收集、JSON 结果解析。
业务代码不要直接 subprocess 拼路径（ADR-0003）。
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.integrate.skill_paths import SkillPaths, resolve_skill_paths


class SkillToolError(RuntimeError):
    def __init__(self, tool: str, returncode: int, stderr: str) -> None:
        super().__init__(f"{tool} failed rc={returncode}: {stderr[:500]}")
        self.tool = tool
        self.returncode = returncode
        self.stderr = stderr


@dataclass(slots=True)
class SkillResult:
    tool: str
    payload: dict[str, Any]
    stdout: str
    stderr: str


def _run_tool(
    script: Path,
    args: list[str],
    *,
    timeout: float = 120.0,
) -> SkillResult:
    cmd = [sys.executable, str(script), *args]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    if proc.returncode != 0:
        raise SkillToolError(script.name, proc.returncode, stderr)

    payload: dict[str, Any] = {}
    text = stdout.strip()
    if text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                payload = parsed
            else:
                payload = {"result": parsed}
        except json.JSONDecodeError:
            payload = {"raw": text}
    return SkillResult(tool=script.name, payload=payload, stdout=stdout, stderr=stderr)


def init_host_run(
    *,
    novel_path: Path,
    characters: list[str],
    output_manifest: Path,
    novel_id: str = "",
    skill: SkillPaths | None = None,
) -> SkillResult:
    skill = skill or resolve_skill_paths()
    args = [
        "--novel",
        str(novel_path),
        "--characters",
        ",".join(characters),
        "--output",
        str(output_manifest),
    ]
    if novel_id:
        args.extend(["--novel-id", novel_id])
    return _run_tool(skill.init_host_run, args)


def build_prompt_payload(
    *,
    novel_path: Path,
    characters: list[str],
    output_payload: Path,
    run_manifest: Path | None = None,
    skill: SkillPaths | None = None,
    timeout: float = 180.0,
) -> SkillResult:
    skill = skill or resolve_skill_paths()
    args = [
        "--mode",
        "distill",
        "--novel",
        str(novel_path),
        "--characters",
        ",".join(characters),
        "--output",
        str(output_payload),
    ]
    if run_manifest is not None:
        args.extend(["--run-manifest", str(run_manifest)])
    return _run_tool(skill.build_prompt_payload, args, timeout=timeout)


def materialize_profile(
    *,
    profile_file: Path,
    output_dir: Path,
    skill: SkillPaths | None = None,
) -> SkillResult:
    skill = skill or resolve_skill_paths()
    args = [
        "--profile-file",
        str(profile_file),
        "--output-dir",
        str(output_dir),
    ]
    return _run_tool(skill.materialize_persona_bundle, args)


def export_relation_graph(
    *,
    rel_file: Path,
    output_json: Path | None = None,
    novel_id: str = "",
    run_manifest: Path | None = None,
    skill: SkillPaths | None = None,
) -> SkillResult:
    skill = skill or resolve_skill_paths()
    args = ["--relations-file", str(rel_file)]
    if novel_id:
        args.extend(["--novel-id", novel_id])
    if output_json is not None:
        args.extend(["--output", str(output_json)])
    if run_manifest is not None:
        args.extend(["--run-manifest", str(run_manifest)])
    return _run_tool(skill.export_relation_graph, args)


def verify_host_workflow(
    *,
    run_manifest: Path,
    skill: SkillPaths | None = None,
) -> SkillResult:
    skill = skill or resolve_skill_paths()
    return _run_tool(skill.verify_host_workflow, ["--run-manifest", str(run_manifest)])
