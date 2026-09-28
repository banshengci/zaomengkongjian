"use client";

import { useState } from "react";
import {
  apiDelete,
  apiPost,
  apiPut,
  type MemoryItem,
  type WorldFact,
} from "@/lib/api";

export function MemoryPanel({
  sessionId,
  items,
  onChange,
}: {
  sessionId: string;
  items: MemoryItem[];
  onChange: () => void;
}) {
  const [text, setText] = useState("");
  const [pinned, setPinned] = useState(true);
  const [error, setError] = useState("");

  async function add() {
    if (!text.trim()) return;
    try {
      await apiPost(`/theater/sessions/${sessionId}/memories`, {
        text: text.trim(),
        category: "story",
        pinned,
      });
      setText("");
      setError("");
      onChange();
    } catch (e) {
      setError(String(e));
    }
  }

  async function toggle(item: MemoryItem) {
    await apiPut(`/theater/sessions/${sessionId}/memories/${item.id}`, {
      enabled: !item.enabled,
      pinned: item.pinned,
    });
    onChange();
  }

  async function pin(item: MemoryItem) {
    await apiPut(`/theater/sessions/${sessionId}/memories/${item.id}`, {
      pinned: !item.pinned,
      enabled: item.enabled,
    });
    onChange();
  }

  async function remove(id: string) {
    await apiDelete(`/theater/sessions/${sessionId}/memories/${id}`);
    onChange();
  }

  async function merge() {
    await apiPost(`/theater/sessions/${sessionId}/memory-quality/merge-duplicates`);
    onChange();
  }

  return (
    <section className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h3 style={{ margin: 0 }}>长期记忆</h3>
        <button className="secondary" onClick={merge}>
          合并重复
        </button>
      </div>
      <p className="muted">钉选与启用中的记忆会进入生成上下文。</p>
      <div className="row">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="例如：两人约定三日后再会"
          onKeyDown={(e) => {
            if (e.key === "Enter") add();
          }}
        />
        <label className="chip" style={{ cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={pinned}
            onChange={(e) => setPinned(e.target.checked)}
          />
          钉选
        </label>
        <button onClick={add}>添加</button>
      </div>
      {error && <p className="status-bad">{error}</p>}
      <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
        {items.map((m) => (
          <div
            key={m.id}
            className="row"
            style={{
              border: "1px solid var(--line)",
              borderRadius: 10,
              padding: "8px 10px",
              opacity: m.enabled ? 1 : 0.5,
            }}
          >
            <span style={{ flex: 1 }}>
              {m.pinned ? "★ " : ""}
              {m.text}
            </span>
            <span className="chip">{m.category}</span>
            <button className="secondary" onClick={() => pin(m)}>
              {m.pinned ? "取消钉" : "钉住"}
            </button>
            <button className="secondary" onClick={() => toggle(m)}>
              {m.enabled ? "停用" : "启用"}
            </button>
            <button className="secondary" onClick={() => remove(m.id)}>
              删
            </button>
          </div>
        ))}
        {!items.length && <p className="muted">还没有记忆。</p>}
      </div>
    </section>
  );
}

export function WorldPanel({
  bookId,
  sessionId,
  view,
  onChange,
}: {
  bookId: string;
  sessionId: string;
  view: { facts: WorldFact[]; timeline: { time_hint: string; location: string; summary: string; locked: boolean }[] };
  onChange: () => void;
}) {
  const [summary, setSummary] = useState("");
  const [timeHint, setTimeHint] = useState("");
  const [location, setLocation] = useState("");
  const [locked, setLocked] = useState(false);
  const [error, setError] = useState("");

  async function add() {
    if (!summary.trim()) return;
    try {
      await apiPost(`/books/${bookId}/world-memory/facts`, {
        category: "event",
        summary: summary.trim(),
        time_hint: timeHint,
        location,
        locked,
      });
      setSummary("");
      setError("");
      onChange();
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <section className="card">
      <h3>世界记忆</h3>
      <p className="muted">
        锁定事实会写入提示词，生成时不可改写。会话 {sessionId.slice(0, 8)} 视图。
      </p>
      <label>事实</label>
      <input
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
        placeholder="旧宅十年前失火"
      />
      <div className="row">
        <input
          value={timeHint}
          onChange={(e) => setTimeHint(e.target.value)}
          placeholder="时间（如：十年前）"
        />
        <input
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          placeholder="地点"
        />
        <label className="chip" style={{ cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={locked}
            onChange={(e) => setLocked(e.target.checked)}
          />
          锁定
        </label>
        <button onClick={add}>记录</button>
      </div>
      {error && <p className="status-bad">{error}</p>}
      <div style={{ marginTop: 12 }}>
        {(view.timeline || []).map((t, i) => (
          <div key={i} className="muted" style={{ marginBottom: 8 }}>
            <strong style={{ color: "var(--ink)" }}>
              {t.time_hint || "未标注"} · {t.location || "—"}
            </strong>
            {t.locked && <span className="chip" style={{ marginLeft: 8 }}>锁定</span>}
            <div>{t.summary}</div>
          </div>
        ))}
        {!view.timeline?.length && <p className="muted">时间轴为空。</p>}
      </div>
    </section>
  );
}
