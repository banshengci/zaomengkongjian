"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, type Chapter } from "@/lib/api";

function SideBySide({ before, after }: { before: string; after: string }) {
  const beforeLines = before.split("\n");
  const afterLines = after.split("\n");
  const max = Math.max(beforeLines.length, afterLines.length);
  const rows: { left: string; right: string; changed: boolean }[] = [];
  for (let i = 0; i < max; i++) {
    const l = beforeLines[i] ?? "";
    const r = afterLines[i] ?? "";
    rows.push({ left: l, right: r, changed: l !== r });
  }
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 12,
        fontFamily: "ui-monospace, monospace",
        fontSize: "0.88rem",
      }}
    >
      <div>
        <h4 className="muted">改写前</h4>
        <div className="card" style={{ minHeight: 200 }}>
          {rows.map((row, i) => (
            <div
              key={`l-${i}`}
              style={{
                background: row.changed ? "rgba(240,180,41,0.12)" : "transparent",
                padding: "2px 6px",
                borderRadius: 4,
              }}
            >
              {row.left || " "}
            </div>
          ))}
        </div>
      </div>
      <div>
        <h4 className="muted">改写后</h4>
        <div className="card" style={{ minHeight: 200 }}>
          {rows.map((row, i) => (
            <div
              key={`r-${i}`}
              style={{
                background: row.changed ? "rgba(110,168,255,0.12)" : "transparent",
                padding: "2px 6px",
                borderRadius: 4,
              }}
            >
              {row.right || " "}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function ChapterDiffPage() {
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [activeId, setActiveId] = useState("");
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [instruction, setInstruction] = useState("加强环境描写，保持情节不变");
  const [context, setContext] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  useEffect(() => {
    apiGet<{ items: Chapter[] }>("/theater/chapters")
      .then((d) => {
        setChapters(d.items || []);
        if (d.items?.length && !activeId) {
          setActiveId(d.items[0].id);
          setChapter(d.items[0]);
        }
      })
      .catch((e) => setError(String(e)));
  }, [activeId]);

  async function pick(id: string) {
    setActiveId(id);
    try {
      setChapter(await apiGet<Chapter>(`/theater/chapters/${id}`));
    } catch (e) {
      setError(String(e));
    }
  }

  async function rewrite() {
    if (!chapter) return;
    setBusy(true);
    setError("");
    setInfo("");
    try {
      const updated = await apiPost<Chapter>(`/theater/chapters/${chapter.id}/rewrite`, {
        instruction,
        context_summary: context,
      });
      setChapter(updated);
      setInfo(`已改写，历史版本 ${updated.revisions?.length ?? 0} 条`);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function continueWrite() {
    if (!chapter) return;
    try {
      const session = await apiPost<{ id: string; title: string }>(
        `/theater/chapters/${chapter.id}/continue`
      );
      setInfo(`已开续写会话：${session.title}`);
    } catch (e) {
      setError(String(e));
    }
  }

  const before = chapter?.revisions?.length
    ? chapter.revisions[chapter.revisions.length - 1].content
    : chapter?.content_md || "";
  const after = chapter?.content_md || "";

  return (
    <div className="grid">
      <section className="card">
        <h3>章节改写</h3>
        <p className="muted">选择章节 → 下指令 → 双栏对照改写前后。</p>
        <div className="row">
          {chapters.map((c) => (
            <button
              key={c.id}
              className={c.id === activeId ? "" : "secondary"}
              onClick={() => pick(c.id)}
            >
              {c.title}
            </button>
          ))}
        </div>
        <label>改写指令</label>
        <input value={instruction} onChange={(e) => setInstruction(e.target.value)} />
        <label>背景摘要（可选）</label>
        <input value={context} onChange={(e) => setContext(e.target.value)} />
        <div className="row" style={{ marginTop: 12 }}>
          <button onClick={rewrite} disabled={busy || !chapter}>
            {busy ? "改写中…" : "改写"}
          </button>
          <button className="secondary" onClick={continueWrite} disabled={!chapter}>
            续写
          </button>
          {info && <span className="status-ok">{info}</span>}
          {error && <span className="status-bad">{error}</span>}
        </div>
      </section>

      {chapter && <SideBySide before={before} after={after} />}
    </div>
  );
}
