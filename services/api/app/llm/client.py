"""LLM 客户端：OpenAI 兼容流式 NDJSON + Mock 回退。"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings


class LlmError(RuntimeError):
    pass


@dataclass(slots=True)
class LlmMessage:
    role: str
    content: str


class LlmClient:
    """对话生成统一入口。无密钥时使用 Mock，保证本地可跑通。"""

    def __init__(
        self, *, base_url: str = "", api_key: str = "", model: str = ""
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self.mock = not (self.base_url and self.api_key and self.model)

    async def complete_text(
        self, messages: list[LlmMessage], *, max_tokens: int = 2048
    ) -> str:
        if self.mock:
            return _mock_complete(messages)
        return await _http_complete(self, messages, max_tokens=max_tokens)

    async def stream_ndjson(
        self, messages: list[LlmMessage], *, max_tokens: int = 2048
    ) -> AsyncIterator[dict[str, Any]]:
        if self.mock:
            for row in _mock_ndjson(messages):
                yield row
            return
        async for row in _http_stream_ndjson(self, messages, max_tokens=max_tokens):
            yield row


def _last_user(messages: list[LlmMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return messages[-1].content if messages else ""


def _mock_complete(messages: list[LlmMessage]) -> str:
    text = _last_user(messages)
    if "PROFILE" in text or "蒸馏" in text or "人物档案" in text:
        name = _guess_name(text) or "角色甲"
        return _mock_profile_md(name)
    if "RELATION" in text or "关系" in text:
        return _mock_relation_md(_guess_names(text))
    return "（mock 模型回复）请配置 DREAMSPACE_LLM_* 以启用真实模型。"


def _guess_name(text: str) -> str:
    m = re.search(r"(?:角色名|name)[:：]\s*([^\n，,。]{1,12})", text)
    return m.group(1).strip() if m else ""


def _guess_names(text: str) -> list[str]:
    m = re.search(r"参与角色[:：]\s*([^\n。]+)", text)
    if m:
        parts = re.split(r"[、,，\s]+", m.group(1).strip())
        names = [p.strip() for p in parts if p.strip() and "历史" not in p]
        if names:
            return names[:4]
    found = re.findall(r"(?:角色|人物)[:：]\s*([^\n，,。]{1,12})", text)
    return [item.strip() for item in found if item.strip()][:4] or ["角色甲", "角色乙"]


def _mock_profile_md(name: str) -> str:
    return f"""# PROFILE
<!-- Canonical markdown profile storage. -->

## Meta
- name: {name}
- novel_id: mock_novel
- timeline_stage: 前期
- role_tags: 核心主角

## Basic Positioning
- core_identity: 原作中可辨识的核心人物
- story_role: 事件推进者
- identity_anchor: 以自身立场与目标定义行动

## Root Layer
- background_imprint: 原作背景对性格形成有持续影响
- trauma_scar: 旧伤仍会影响其反应方式

## Inner Core
- soul_goal: 守住自我认定的核心目标
- core_traits: 敏锐；克制
- values: 勇气=6；智慧=7；善良=6

## External Persona
- appearance_feature: 原作可见外在标识
- habit_action: 习惯性小动作

## Voice
- speech_style: 语气克制，带个人口癖
- signature_phrases: 原是；何必

## Capability
- strengths: 观察细致
- weaknesses: 易内耗

## Arc
- arc_type: 觉醒

## Performance Boundary
- ooc_redline: 不会违背原作核心设定底线

## Evidence
- description_count: 1
- dialogue_count: 1
- thought_count: 0
- chunk_count: 1
- evidence_source: S000001
- contradiction_note:
"""


def _mock_relation_md(names: list[str]) -> str:
    lines = ["# RELATION_GRAPH", ""]
    if len(names) >= 2:
        a, b = names[0], names[1]
        lines += [
            f"## {a}_{b}",
            "- trust: 6",
            "- affection: 5",
            "- power_gap: 1",
            "- conflict_point: 立场差异",
            "- typical_interaction: 试探->回应",
            "- relation_change: 大体稳定",
            f"- appellation_to_target: {b}",
            "- confidence: 6",
            "",
        ]
    else:
        lines += [
            "## 角色甲_角色乙",
            "- trust: 5",
            "- affection: 4",
            "- power_gap: 0",
            "",
        ]
    return "\n".join(lines)


def _all_text(messages: list[LlmMessage]) -> str:
    return "\n".join(m.content for m in messages)


def _mock_ndjson(messages: list[LlmMessage]) -> list[dict[str, Any]]:
    text = _all_text(messages)
    names = _guess_names(text)
    return [
        {"speaker": names[0], "message": "……你来了。"},
        {"speaker": names[1] if len(names) > 1 else "旁白", "message": "风声渐紧。"},
    ]


async def _http_complete(
    client: LlmClient, messages: list[LlmMessage], *, max_tokens: int
) -> str:
    payload = {
        "model": client.model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=120.0) as http:
        resp = await http.post(
            f"{client.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {client.api_key}"},
            json=payload,
        )
        if resp.status_code >= 400:
            raise LlmError(f"llm http {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _http_stream_ndjson(
    client: LlmClient, messages: list[LlmMessage], *, max_tokens: int
) -> AsyncIterator[dict[str, Any]]:
    payload = {
        "model": client.model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "stream": True,
    }
    buffer = ""
    async with (
        httpx.AsyncClient(timeout=None) as http,
        http.stream(
            "POST",
            f"{client.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {client.api_key}"},
            json=payload,
        ) as resp,
    ):
        if resp.status_code >= 400:
            body = await resp.aread()
            raise LlmError(f"llm http {resp.status_code}: {body[:300]!r}")
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            chunk = line[5:].strip()
            if chunk == "[DONE]":
                break
            try:
                obj = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            delta = obj.get("choices", [{}])[0].get("delta", {})
            content = delta.get("content") or ""
            if not content:
                continue
            buffer += content
            while "\n" in buffer:
                raw, buffer = buffer.split("\n", 1)
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError:
                    continue
    tail = buffer.strip()
    if tail:
        try:
            yield json.loads(tail)
        except json.JSONDecodeError:
            yield {"speaker": "旁白", "message": tail}
