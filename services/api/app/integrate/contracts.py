"""契约解析：人物 PROFILE / 关系图 / 书卷包 manifest。

这些解析器只认造梦 canonical 形状；产品扩展键不参与校验失败。
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


class ProfileParseError(ValueError):
    pass


class ProfileMeta(BaseModel):
    name: str = ""
    novel_id: str = ""
    timeline_stage: str = ""
    role_tags: list[str] = Field(default_factory=list)


class ParsedProfile(BaseModel):
    meta: ProfileMeta
    sections: dict[str, dict[str, str]] = Field(default_factory=dict)
    raw: str = ""

    @property
    def name(self) -> str:
        return self.meta.name


_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_FIELD_RE = re.compile(r"^-\s+([A-Za-z0-9_]+)\s*:\s*(.*)$")


def parse_profile_markdown(text: str) -> ParsedProfile:
    """解析造梦 `# PROFILE` markdown（output_schema.md 形状）。"""
    if not text or not text.strip():
        raise ProfileParseError("empty profile text")
    if not re.search(r"^#\s+PROFILE\s*$", text, re.MULTILINE):
        raise ProfileParseError("missing # PROFILE heading")

    sections: dict[str, dict[str, str]] = {}
    current: str = ""
    for line in text.splitlines():
        sec = _SECTION_RE.match(line)
        if sec:
            current = sec.group(1).strip()
            sections.setdefault(current, {})
            continue
        if not current:
            continue
        field = _FIELD_RE.match(line.strip())
        if field:
            sections[current][field.group(1)] = field.group(2).strip()

    meta_fields = sections.get("Meta", {})
    name = meta_fields.get("name", "").strip()
    if not name:
        raise ProfileParseError("PROFILE.Meta.name is empty")

    role_raw = meta_fields.get("role_tags", "")
    role_tags = [part.strip() for part in role_raw.split("；") if part.strip()]

    return ParsedProfile(
        meta=ProfileMeta(
            name=name,
            novel_id=meta_fields.get("novel_id", "").strip(),
            timeline_stage=meta_fields.get("timeline_stage", "").strip(),
            role_tags=role_tags,
        ),
        sections=sections,
        raw=text,
    )


def extract_values_scale(sections: dict[str, dict[str, str]]) -> dict[str, int]:
    """从 Inner Core.values 抽取 0–10 标尺；非法项跳过。"""
    raw = sections.get("Inner Core", {}).get("values", "")
    result: dict[str, int] = {}
    for part in raw.split("；"):
        if "=" not in part:
            continue
        key, _, val = part.partition("=")
        key = key.strip()
        val = val.strip()
        if not key or not val.lstrip("-").isdigit():
            continue
        num = int(val)
        if 0 <= num <= 10:
            result[key] = num
    return result


class RelationEdge(BaseModel):
    pair_key: str
    fields: dict[str, str] = Field(default_factory=dict)


def parse_relation_markdown(text: str) -> list[RelationEdge]:
    """解析 `# RELATION_GRAPH` 下的 `## A_B` 段落。"""
    edges: list[RelationEdge] = []
    current: RelationEdge | None = None
    in_graph = False
    for line in text.splitlines():
        if line.strip() == "# RELATION_GRAPH":
            in_graph = True
            continue
        if line.startswith("## "):
            pair = line[3:].strip()
            current = RelationEdge(pair_key=pair)
            edges.append(current)
            continue
        if current is None:
            continue
        field = _FIELD_RE.match(line.strip())
        if field:
            current.fields[field.group(1)] = field.group(2).strip()
    if not in_graph and not edges:
        raise ProfileParseError("missing RELATION_GRAPH heading and pairs")
    return edges


class PackageManifest(BaseModel):
    kind: str = "zaomeng_web_run_package"
    schema_version: int = 1
    package_id: str = ""
    title: str = ""
    novel_id: str = ""
    character_count: int = 0
    has_relation_graph: bool = False
    includes_dialogue: bool = False
    includes_chapters: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


def normalize_package_manifest(data: dict[str, Any]) -> PackageManifest:
    """对齐 data-dictionary 的 v0→v1 归一规则；未知版本拒绝。"""
    if not isinstance(data, dict):
        raise ProfileParseError("package manifest must be object")
    version = data.get("schema_version", 0)
    try:
        version_int = int(version)
    except (TypeError, ValueError) as exc:
        raise ProfileParseError("schema_version must be int") from exc
    if version_int not in (0, 1):
        raise ProfileParseError(f"unsupported schema_version: {version_int}")

    summary = data.get("summary") or {}
    if not isinstance(summary, dict):
        summary = {}

    status_text = summary.get("status_text") or data.get("status") or ""
    graph_status = summary.get("graph_status")
    if not graph_status:
        graph_status = "complete" if data.get("has_relation_graph") else "pending"

    builtin = data.get("builtin")
    if builtin is None:
        builtin = False

    try:
        character_count = int(data.get("character_count") or 0)
    except (TypeError, ValueError):
        character_count = 0

    known = {
        "kind",
        "schema_version",
        "package_id",
        "title",
        "novel_id",
        "character_count",
        "has_relation_graph",
        "includes_dialogue",
        "includes_chapters",
    }
    extra = {k: v for k, v in data.items() if k not in known and k != "summary"}
    extra["status_text"] = status_text
    extra["graph_status"] = graph_status
    extra["builtin"] = bool(builtin)

    return PackageManifest(
        kind=str(data.get("kind") or "zaomeng_web_run_package"),
        schema_version=1,
        package_id=str(data.get("package_id") or ""),
        title=str(data.get("title") or ""),
        novel_id=str(data.get("novel_id") or ""),
        character_count=max(0, character_count),
        has_relation_graph=bool(data.get("has_relation_graph")),
        includes_dialogue=bool(data.get("includes_dialogue")),
        includes_chapters=bool(data.get("includes_chapters")),
        extra=extra,
    )
