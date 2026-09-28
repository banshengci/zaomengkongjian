"""契约测试：PROFILE / 关系 / 书卷包 manifest（docs/contract-tests.md）。"""

from __future__ import annotations

import pytest

from app.integrate.contracts import (
    ProfileParseError,
    extract_values_scale,
    normalize_package_manifest,
    parse_profile_markdown,
    parse_relation_markdown,
)

SAMPLE_PROFILE = """# PROFILE
<!-- Canonical markdown profile storage. -->

## Meta
- name: 林黛玉
- novel_id: sample_novel
- source_path: data/sample_novel.txt
- timeline_stage: 前期
- role_tags: 核心主角；悲剧型；群像核心

## Basic Positioning
- core_identity: 才情出众、情思纤细的核心人物
- story_role: 以情感锋芒推动人物关系张力

## Inner Core
- soul_goal: 守住自尊与真情
- core_traits: 敏感；聪慧；自尊
- values: 勇气=6；智慧=8；善良=7

## Voice
- speech_style: 言辞锋利但情绪克制
- signature_phrases: 原是；何必

## Evidence
- description_count: 1
- dialogue_count: 2
- evidence_source: S000123；S000456
"""

SAMPLE_RELATION = """# RELATION_GRAPH

## 林黛玉_贾宝玉
- trust: 7
- affection: 8
- power_gap: 1
- conflict_point: 表达方式与误解
- typical_interaction: 黛玉质问->宝玉安抚

## 林黛玉_薛宝钗
- trust: 6
- affection: 6
- power_gap: 0
- conflict_point: 价值观差异
"""


def test_profile_requires_heading() -> None:
    with pytest.raises(ProfileParseError):
        parse_profile_markdown("name: foo\n")


def test_profile_parse_meta_and_sections() -> None:
    parsed = parse_profile_markdown(SAMPLE_PROFILE)
    assert parsed.name == "林黛玉"
    assert parsed.meta.novel_id == "sample_novel"
    assert "核心主角" in parsed.meta.role_tags
    assert "Meta" in parsed.sections
    assert "Voice" in parsed.sections
    assert parsed.sections["Voice"]["speech_style"].startswith("言辞锋利")


def test_profile_values_scale_bounds() -> None:
    parsed = parse_profile_markdown(SAMPLE_PROFILE)
    scale = extract_values_scale(parsed.sections)
    assert scale == {"勇气": 6, "智慧": 8, "善良": 7}
    assert all(0 <= v <= 10 for v in scale.values())


def test_relation_pairs_and_fields() -> None:
    edges = parse_relation_markdown(SAMPLE_RELATION)
    assert len(edges) == 2
    assert edges[0].pair_key == "林黛玉_贾宝玉"
    assert edges[0].fields["trust"] == "7"
    assert edges[1].fields["conflict_point"] == "价值观差异"


def test_package_manifest_v1_passthrough() -> None:
    manifest = normalize_package_manifest(
        {
            "kind": "zaomeng_web_run_package",
            "schema_version": 1,
            "package_id": "pkg-1",
            "title": "红楼",
            "novel_id": "honglou",
            "character_count": 3,
            "has_relation_graph": True,
            "summary": {"status_text": "ready", "graph_status": "complete"},
        }
    )
    assert manifest.schema_version == 1
    assert manifest.character_count == 3
    assert manifest.extra["status_text"] == "ready"
    assert manifest.extra["graph_status"] == "complete"
    assert manifest.extra["builtin"] is False


def test_package_manifest_v0_normalized() -> None:
    manifest = normalize_package_manifest(
        {
            "schema_version": 0,
            "package_id": "pkg-0",
            "has_relation_graph": True,
        }
    )
    assert manifest.schema_version == 1
    assert manifest.extra["graph_status"] == "complete"
    assert manifest.extra["builtin"] is False
    assert manifest.character_count == 0


def test_package_manifest_unknown_version_rejected() -> None:
    with pytest.raises(ProfileParseError):
        normalize_package_manifest({"schema_version": 2})


def test_extension_fields_are_namespaced() -> None:
    # 产品扩展键必须 x_dreamspace_ 前缀（C-X-01）；解析层不因未知键失败
    parsed = parse_profile_markdown(SAMPLE_PROFILE + "- x_dreamspace_color: rose\n")
    assert parsed.name == "林黛玉"
