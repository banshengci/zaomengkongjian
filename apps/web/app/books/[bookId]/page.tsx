"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  apiGet,
  apiPost,
  type Book,
  type Character,
  type MemoryItem,
  type Relation,
  type Session,
  type SessionTreeNode,
  type TurnMessage,
  type WorldFact,
} from "@/lib/api";
import BranchTimeline from "@/components/theater/BranchTimeline";
import { MemoryPanel, WorldPanel } from "@/components/theater/MemoryPanels";
import { EvolvePanel, SeatPanel } from "@/components/theater/CollabPanels";

export default function BookDetailPage() {
  const params = useParams<{ bookId: string }>();
  const bookId = params.bookId;
  const [book, setBook] = useState<Book | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [relations, setRelations] = useState<Relation[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [tree, setTree] = useState<SessionTreeNode[]>([]);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [world, setWorld] = useState<{
    facts: WorldFact[];
    timeline: { time_hint: string; location: string; summary: string; locked: boolean }[];
  }>({ facts: [], timeline: [] });
  const [selected, setSelected] = useState<string[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<(TurnMessage & { source: "user" | "ai" })[]>([]);
  const [selectedIdx, setSelectedIdx] = useState<number[]>([]);
  const [input, setInput] = useState("");
  const [sceneTitle, setSceneTitle] = useState("雨夜对谈");
  const [sceneCards, setSceneCards] = useState<{ id: string; title: string; preview: string }[]>([]);
  const [sceneCardId, setSceneCardId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [b, c, r, s, t, cards] = await Promise.all([
        apiGet<Book>(`/books/${bookId}`),
        apiGet<{ items: Character[] }>(`/books/${bookId}/characters`),
        apiGet<{ items: Relation[] }>(`/books/${bookId}/relations`),
        apiGet<Session[]>(`/theater/sessions?book_id=${bookId}`),
        apiGet<SessionTreeNode[]>(`/theater/sessions/tree?book_id=${bookId}`),
        apiGet<{ items: { id: string; title: string; preview: string }[] }>(`/scene-cards`),
      ]);
      setBook(b);
      setCharacters(c.items || []);
      setRelations(r.items || []);
      setSessions(s || []);
      setTree(t || []);
      setSceneCards(cards.items || []);
      setTree(t || []);
      if (!selected.length && c.items?.length) {
        setSelected(c.items.slice(0, 2).map((x) => x.name));
      }
    } catch (e) {
      setError(String(e));
    }
  }, [bookId, selected.length]);

  const loadSessionSide = useCallback(async (sid: string) => {
    try {
      const [m, w] = await Promise.all([
        apiGet<MemoryItem[]>(`/theater/sessions/${sid}/memories`),
        apiGet<{ facts: WorldFact[]; timeline: { time_hint: string; location: string; summary: string; locked: boolean }[] }>(
          `/theater/sessions/${sid}/world-memory`
        ),
      ]);
      setMemories(m || []);
      setWorld(w || { facts: [], timeline: [] });
    } catch {
      setMemories([]);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (session) loadSessionSide(session.id);
  }, [session, loadSessionSide]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const relationPairs = useMemo(() => relations.slice(0, 8), [relations]);

  async function createSession(title?: string) {
    setBusy(true);
    setError("");
    try {
      const s = await apiPost<Session>("/theater/sessions", {
        book_id: bookId,
        mode: "observe",
        participants: selected,
        title: title || sceneTitle,
        scene_card_id: sceneCardId,
      });
      setSession(s);
      setMessages([]);
      setSelectedIdx([]);
      await loadAll();
      await loadSessionSide(s.id);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function branch(label: string) {
    if (!session) return;
    setBusy(true);
    try {
      const child = await apiPost<Session>(`/theater/sessions/${session.id}/branch`, {
        label,
        turn_id: "",
      });
      setSession(child);
      setSelectedIdx([]);
      try {
        const hist = await apiGet<{ items: TurnMessage[] }>(
          `/theater/sessions/${child.id}/messages`
        );
        setMessages(
          (hist.items || []).map((m) => ({
            ...m,
            source: m.role === "user" ? "user" : "ai",
          }))
        );
      } catch {
        setMessages([]);
      }
      setInfo(`已开支线：${child.title}`);
      await loadAll();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function pickSession(id: string) {
    const s =
      sessions.find((x) => x.id === id) ||
      (await apiGet<Session>(`/theater/sessions/${id}`));
    setSession(s);
    setSelectedIdx([]);
    try {
      const hist = await apiGet<{ items: TurnMessage[] }>(
        `/theater/sessions/${id}/messages`
      );
      setMessages(
        (hist.items || []).map((m) => ({
          ...m,
          source: m.role === "user" ? "user" : "ai",
        }))
      );
    } catch {
      setMessages([]);
    }
    await loadSessionSide(id);
  }

  async function send() {
    if (!session || !input.trim()) return;
    const text = input.trim();
    setInput("");
    setMessages((prev) => [
      ...prev,
      { speaker: "你", message: text, role: "user", source: "user" },
    ]);
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/api/v1/theater/sessions/${session.id}/reply/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          message_kind: "dialogue",
          operation_id: `op-${Date.now()}`,
        }),
      });
      if (!res.ok || !res.body) throw new Error(await res.text());
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const acc: Record<string, { speaker: string; message: string }> = {};
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() || "";
        for (const chunk of chunks) {
          const line = chunk.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          const data = JSON.parse(line.slice(5).trim());
          if (data.speaker && data.text) {
            acc[data.speaker] = acc[data.speaker] || { speaker: data.speaker, message: "" };
            acc[data.speaker].message += data.text;
            const merged = Object.values(acc).map((m) => ({
              ...m,
              role: "character",
              source: "ai" as const,
            }));
            setMessages((prev) => {
              const kept = prev.filter((m) => m.source !== "ai");
              return [...kept, ...merged];
            });
          }
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
      await loadAll();
      if (session) await loadSessionSide(session.id);
    }
  }

  async function runDirector(action: string) {
    if (!session) return;
    try {
      const data = await apiPost<{
        options: { id: string; title: string; detail: string }[];
      }>(`/theater/sessions/${session.id}/director`, {
        goal: "推进剧情",
        action,
        option_count: 3,
      });
      setInfo(data.options.map((o) => `${o.title}：${o.detail}`).join("\n"));
    } catch (e) {
      setError(String(e));
    }
  }

  async function archive() {
    if (!session) return;
    try {
      const chapter = await apiPost<{ id: string; title: string }>(
        `/theater/sessions/${session.id}/archive`,
        { session_id: session.id, title: sceneTitle || "章节" }
      );
      const share = await apiPost<{ token: string; url_path: string }>(`/theater/share`, {
        resource_type: "chapter",
        resource_id: chapter.id,
        expires_hours: 72,
      });
      setInfo(`已归档《${chapter.title}》，分享 ${share.url_path}`);
    } catch (e) {
      setError(String(e));
    }
  }

  async function makeHighlight() {
    if (!session || !selectedIdx.length) {
      setInfo("先勾选要放进名场面的台词");
      return;
    }
    try {
      const card = await apiPost<{ id: string; share_token: string; title: string }>(
        "/theater/highlights",
        {
          session_id: session.id,
          message_indexes: selectedIdx,
          title: sceneTitle || "名场面",
        }
      );
      setInfo(`名场面已生成，分享路径 /share/${card.share_token}`);
    } catch (e) {
      setError(String(e));
    }
  }

  async function exportBook() {
    try {
      const res = await fetch(`/api/v1/books/${bookId}/export?include_dialogue=1&include_chapters=1`);
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${bookId}.zaomeng.zip`;
      a.click();
      URL.revokeObjectURL(url);
      setInfo("书卷包已导出");
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div className="grid">
      <section className="card">
        <h3>{book?.title || "书卷"}</h3>
        <p className="muted">
          状态 {book?.status || "…"} · 角色 {characters.length} · 关系 {relations.length}
        </p>
        <div className="row">
          {characters.map((c) => (
            <label key={c.id} className="chip" style={{ cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={selected.includes(c.name)}
                onChange={(e) => {
                  setSelected((prev) =>
                    e.target.checked ? [...prev, c.name] : prev.filter((n) => n !== c.name)
                  );
                }}
              />
              {c.name}
            </label>
          ))}
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <input
            style={{ maxWidth: 240 }}
            value={sceneTitle}
            onChange={(e) => setSceneTitle(e.target.value)}
            placeholder="剧场标题"
          />
          <select
            style={{ maxWidth: 220 }}
            value={sceneCardId}
            onChange={(e) => setSceneCardId(e.target.value)}
          >
            <option value="">不使用场景卡</option>
            {sceneCards.map((card) => (
              <option key={card.id} value={card.id}>
                {card.title}
              </option>
            ))}
          </select>
          <button onClick={() => createSession()} disabled={busy || !selected.length}>
            开启剧场
          </button>
          <button className="secondary" onClick={exportBook}>
            导出书卷包
          </button>
          {sessions.slice(0, 6).map((s) => (
            <button key={s.id} className="secondary" onClick={() => pickSession(s.id)}>
              {s.title}
            </button>
          ))}
        </div>
      </section>

      <div className="theater">
        <section className="stage">
          {!session && <p className="muted">选择角色后开启剧场，即可多角色对话。</p>}
          {messages.map((m, idx) => (
            <div key={`${m.speaker}-${idx}`} style={{ display: "flex", gap: 8 }}>
              <input
                type="checkbox"
                checked={selectedIdx.includes(idx)}
                onChange={(e) => {
                  setSelectedIdx((prev) =>
                    e.target.checked ? [...prev, idx] : prev.filter((i) => i !== idx)
                  );
                }}
              />
              <div
                className={`bubble ${
                  m.role === "user" ? "user" : m.role === "narration" ? "narration" : "character"
                }`}
                style={{ flex: 1 }}
              >
                <div className="speaker">{m.role === "narration" ? "旁白" : m.speaker}</div>
                <div>{m.message}</div>
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
          {session && (
            <div className="row" style={{ marginTop: "auto" }}>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="说点什么…"
                onKeyDown={(e) => {
                  if (e.key === "Enter") send();
                }}
              />
              <button onClick={send} disabled={busy}>
                发送
              </button>
              <button className="secondary" onClick={makeHighlight}>
                名场面
              </button>
            </div>
          )}
        </section>

        <aside style={{ display: "grid", gap: 12 }}>
          <BranchTimeline
            tree={tree}
            activeId={session?.id || ""}
            onPick={pickSession}
            onBranch={branch}
            busy={busy}
          />

          <section className="card">
            <h3>关系速览</h3>
            {relationPairs.map((r) => (
              <div key={r.pair_key} className="muted" style={{ marginBottom: 8 }}>
                <strong style={{ color: "var(--ink)" }}>{r.pair_key}</strong>
                <div>
                  信任 {r.trust} · 亲昵 {r.affection}
                </div>
                <div>{r.conflict_point}</div>
              </div>
            ))}
            <h3 style={{ marginTop: 16 }}>导演</h3>
            <div className="row">
              <button className="secondary" onClick={() => runDirector("advance")}>
                推进
              </button>
              <button className="secondary" onClick={() => runDirector("conflict")}>
                冲突
              </button>
              <button className="secondary" onClick={() => runDirector("slow_emotion")}>
                情绪
              </button>
              <button className="secondary" onClick={() => runDirector("fourth_wall")}>
                第四面墙
              </button>
            </div>
            <button style={{ marginTop: 12 }} onClick={archive} disabled={!session}>
              归档并分享
            </button>
          </section>

          {session && (
            <MemoryPanel
              sessionId={session.id}
              items={memories}
              onChange={() => loadSessionSide(session.id)}
            />
          )}
          {session && (
            <WorldPanel
              bookId={bookId}
              sessionId={session.id}
              view={world}
              onChange={() => loadSessionSide(session.id)}
            />
          )}
          {session && selected[0] && (
            <EvolvePanel
              bookId={bookId}
              character={selected[0]}
              sessionId={session.id}
            />
          )}
          {session && (
            <SeatPanel sessionId={session.id} participants={session.participants} />
          )}

          {info && (
            <pre className="muted" style={{ whiteSpace: "pre-wrap" }}>
              {info}
            </pre>
          )}
          {error && <p className="status-bad">{error}</p>}
        </aside>
      </div>
    </div>
  );
}
