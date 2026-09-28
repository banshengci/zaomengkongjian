"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, type Book } from "@/lib/api";

export default function CrossoverPage() {
  const [books, setBooks] = useState<Book[]>([]);
  const [title, setTitle] = useState("群英会");
  const [worldSetting, setWorldSetting] = useState("众人在一座与原作隔离的客栈相遇。");
  const [rows, setRows] = useState<{ run_id: string; character: string }[]>([
    { run_id: "", character: "" },
    { run_id: "", character: "" },
  ]);
  const [cast, setCast] = useState<Record<string, string[]>>({});
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  useEffect(() => {
    apiGet<Book[]>("/books")
      .then((list) => {
        setBooks(list || []);
        return Promise.all(
          (list || []).map((b) =>
            apiGet<{ items: { name: string }[] }>(`/books/${b.id}/characters`)
              .then((c) => [b.id, (c.items || []).map((x) => x.name)] as const)
              .catch(() => [b.id, [] as string[]] as const)
          )
        );
      })
      .then((pairs) => {
        const map: Record<string, string[]> = {};
        for (const [id, names] of pairs) map[id] = names;
        setCast(map);
      })
      .catch((e) => setError(String(e)));
  }, []);

  async function create() {
    setError("");
    setInfo("");
    try {
      const space = await apiPost<{ id: string; session_id: string; title: string }>(
        "/theater/crossover-spaces",
        {
          title,
          world_setting: worldSetting,
          participants: rows.filter((r) => r.run_id && r.character),
        }
      );
      setInfo(`已创建 ${space.title}（${space.id}），会话 ${space.session_id}`);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <section className="card" style={{ maxWidth: 720 }}>
      <h3>跨作品 Crossover</h3>
      <p className="muted">至少两本书各出一名角色，同台演一幕。</p>
      <label>空间标题</label>
      <input value={title} onChange={(e) => setTitle(e.target.value)} />
      <label>世界设定</label>
      <textarea
        value={worldSetting}
        onChange={(e) => setWorldSetting(e.target.value)}
      />
      {rows.map((row, idx) => (
        <div key={idx} className="row" style={{ marginTop: 8 }}>
          <select
            value={row.run_id}
            onChange={(e) => {
              const run_id = e.target.value;
              setRows((prev) =>
                prev.map((r, i) => (i === idx ? { ...r, run_id, character: "" } : r))
              );
            }}
          >
            <option value="">选择书卷</option>
            {books.map((b) => (
              <option key={b.id} value={b.id}>
                {b.title}
              </option>
            ))}
          </select>
          <select
            value={row.character}
            onChange={(e) => {
              const character = e.target.value;
              setRows((prev) =>
                prev.map((r, i) => (i === idx ? { ...r, character } : r))
              );
            }}
          >
            <option value="">选择角色</option>
            {(cast[row.run_id] || []).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
      ))}
      <div className="row" style={{ marginTop: 12 }}>
        <button
          className="secondary"
          onClick={() => setRows((prev) => [...prev, { run_id: "", character: "" }])}
        >
          加一席
        </button>
        <button onClick={create}>创建群英会</button>
        {info && <span className="status-ok">{info}</span>}
        {error && <span className="status-bad">{error}</span>}
      </div>
    </section>
  );
}
