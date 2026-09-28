"""API / 领域模型 v0.3：分支、记忆、世界、协作、导出、配额。"""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


# ---------- 书卷 ----------


class BookCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    source: Literal["upload", "import"] = "upload"
    novel_id: str = ""
    content: str = Field(default="", max_length=5_000_000)
    x_dreamspace_note: str = ""


class BookRead(BaseModel):
    id: str
    title: str
    source: Literal["upload", "import"] = "upload"
    novel_id: str = ""
    status: Literal["draft", "distilling", "ready", "failed"] = "draft"
    owner_id: str = "anon"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DistillRequest(BaseModel):
    characters: list[str] = Field(min_length=1, max_length=20)
    x_dreamspace_note: str = ""


class DistillJobRead(BaseModel):
    id: str
    book_id: str
    characters: list[str]
    stage: Literal[
        "queued", "running", "merge", "materialize", "graph", "done", "failed"
    ] = "queued"
    progress: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CharacterRead(BaseModel):
    id: str
    book_id: str
    name: str
    profile_ref: str = ""
    role_tags: list[str] = Field(default_factory=list)
    avatar_version: str = ""
    profile: dict[str, Any] = Field(default_factory=dict)
    evolution_log: list[dict[str, Any]] = Field(default_factory=list)


class RelationEdgeRead(BaseModel):
    pair_key: str
    trust: int = 0
    affection: int = 0
    power_gap: int = 0
    hostility: int = 0
    ambiguity: int = 0
    relationship_type: str = ""
    conflict_point: str = ""
    typical_interaction: str = ""
    relation_change: str = ""
    fields: dict[str, str] = Field(default_factory=dict)


class SceneCardRead(BaseModel):
    id: str
    title: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)
    preview: str = ""


# ---------- 剧场 / 分支 ----------


class SessionCreateRequest(BaseModel):
    book_id: str
    mode: Literal["observe", "act", "insert"] = "observe"
    participants: list[str] = Field(min_length=1, max_length=12)
    controlled_character: str = ""
    scene_card_id: str = ""
    self_card_id: str = ""
    title: str = ""
    branch_of: str = ""
    branch_label: str = ""
    x_dreamspace_note: str = ""


class BranchRequest(BaseModel):
    turn_id: str = ""
    scene_index: int | None = None
    label: str = Field(default="", max_length=120)
    locked_event_ids: list[str] = Field(default_factory=list)
    is_mainline: bool = False


class SessionRead(BaseModel):
    id: str
    book_id: str
    title: str = ""
    mode: Literal["observe", "act", "insert"] = "observe"
    participants: list[str] = Field(default_factory=list)
    controlled_character: str = ""
    scene_card_id: str = ""
    self_card_id: str = ""
    status: Literal["idle", "running", "failed"] = "idle"
    transcript_count: int = 0
    branch_of: str = ""
    branch_label: str = ""
    is_mainline: bool = True
    locked_event_ids: list[str] = Field(default_factory=list)
    x_dreamspace_crossover: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SessionTreeNode(BaseModel):
    id: str
    title: str
    branch_of: str = ""
    branch_label: str = ""
    is_mainline: bool = True
    transcript_count: int = 0
    children: list["SessionTreeNode"] = Field(default_factory=list)


class TurnMessage(BaseModel):
    speaker: str
    message: str
    inner_thought: str = ""
    role: Literal["character", "narration", "user", "system"] = "character"


class TurnCreateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    message_kind: Literal["dialogue", "narration", "plot", "fourth_wall"] = "dialogue"
    pacing: Literal["brief", "normal", "detailed"] = "normal"
    include_inner_thoughts: bool = False
    operation_id: str = ""


class TurnRead(BaseModel):
    id: str
    session_id: str
    operation_id: str = ""
    status: Literal["pending", "streaming", "committed", "failed"] = "pending"
    messages: list[TurnMessage] = Field(default_factory=list)
    error: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class DirectorRequest(BaseModel):
    goal: str = Field(default="", max_length=400)
    action: Literal[
        "advance", "slow_emotion", "conflict", "viewpoint", "fourth_wall"
    ] = "advance"
    option_count: int = Field(default=3, ge=2, le=4)


class DirectorOption(BaseModel):
    id: str
    action: str
    title: str
    detail: str = ""
    message_kind: str = "dialogue"


# ---------- 记忆 / 世界 ----------


class MemoryCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    category: Literal["story", "relation", "ooc", "world"] = "story"
    pinned: bool = False
    enabled: bool = True


class MemoryRead(BaseModel):
    id: str
    session_id: str
    text: str
    category: Literal["story", "relation", "ooc", "world"] = "story"
    pinned: bool = False
    enabled: bool = True
    status: Literal["active", "stale", "conflict"] = "active"
    source: str = "manual"
    source_turn_id: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class WorldFactRequest(BaseModel):
    category: Literal["event", "place", "rule", "other"] = "event"
    summary: str = Field(min_length=1, max_length=500)
    characters: list[str] = Field(default_factory=list)
    location: str = Field(default="", max_length=100)
    time_hint: str = Field(default="", max_length=80)
    locked: bool = False
    active: bool = True


class WorldFactRead(BaseModel):
    id: str
    book_id: str
    category: str = "event"
    summary: str
    characters: list[str] = Field(default_factory=list)
    location: str = ""
    time_hint: str = ""
    locked: bool = False
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)


# ---------- 章节 ----------


class ChapterCreateRequest(BaseModel):
    session_id: str
    title: str = ""


class ChapterRewriteRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=1000)
    context_summary: str = Field(default="", max_length=2000)


class ChapterRead(BaseModel):
    id: str
    book_id: str
    session_id: str = ""
    title: str = ""
    content_md: str = ""
    revisions: list[dict[str, str]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


# ---------- 分享 / 名场面 ----------


class ShareCreateRequest(BaseModel):
    resource_type: Literal["session", "chapter", "highlight"] = "session"
    resource_id: str
    expires_hours: int = Field(default=72, ge=1, le=24 * 30)


class ShareLinkRead(BaseModel):
    token: str
    url_path: str
    resource_type: str
    resource_id: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=utc_now)


class HighlightCardRequest(BaseModel):
    session_id: str
    message_indexes: list[int] = Field(min_length=1, max_length=20)
    title: str = Field(default="名场面", max_length=60)


class HighlightCardRead(BaseModel):
    id: str
    session_id: str
    title: str
    lines: list[TurnMessage]
    share_token: str = ""
    created_at: datetime = Field(default_factory=utc_now)


# ---------- Crossover / 协作 / 演进 ----------


class CrossoverCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    world_setting: str = Field(default="", max_length=2000)
    participants: list[dict[str, str]] = Field(min_length=2, max_length=8)


class CrossoverSpaceRead(BaseModel):
    id: str
    title: str
    world_setting: str = ""
    participants: list[dict[str, str]] = Field(default_factory=list)
    session_id: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class SeatClaimRequest(BaseModel):
    character: str = Field(min_length=1, max_length=40)
    display_name: str = Field(default="", max_length=40)


class SessionMemberRead(BaseModel):
    user_id: str
    display_name: str = ""
    character: str = ""
    role: Literal["director", "actor", "viewer"] = "actor"
    online: bool = True


class EvolveProposalRequest(BaseModel):
    session_id: str = ""
    focus: str = Field(default="", max_length=200)


class EvolveApplyRequest(BaseModel):
    fields: dict[str, str] = Field(default_factory=dict)
    note: str = Field(default="", max_length=200)


class EvolveProposalRead(BaseModel):
    id: str
    book_id: str
    character: str
    fields: dict[str, str] = Field(default_factory=dict)
    rationale: str = ""
    status: Literal["proposed", "applied", "rejected"] = "proposed"
    created_at: datetime = Field(default_factory=utc_now)


# ---------- 账号 / 配额 ----------


class AuthAnonRequest(BaseModel):
    display_name: str = Field(default="旅人", max_length=40)


class AuthAnonResponse(BaseModel):
    user_id: str
    token: str
    display_name: str


class QuotaStatus(BaseModel):
    user_id: str
    distill_used: int = 0
    distill_limit: int = 20
    turn_used: int = 0
    turn_limit: int = 200
    reset_at: datetime


# ---------- 设置 ----------


class ModelSettingsRead(BaseModel):
    provider: str = "openai-compatible"
    model: str = ""
    base_url: str = ""
    api_key_configured: bool = False
    max_tokens: int = 4096


class ModelSettingsWrite(BaseModel):
    provider: str = "openai-compatible"
    model: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=400)
    api_key: str = Field(default="", max_length=400)
    max_tokens: int = Field(default=4096, ge=256, le=32768)


class ModelConnectionTest(BaseModel):
    ok: bool = False
    latency_ms: int = 0
    message: str = ""
