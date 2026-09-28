"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, type QuotaStatus } from "@/lib/api";

export default function HomePage() {
  const [books, setBooks] = useState<{ id: string; title: string; status: string; novel_id: string }[]>([]);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [characters, setCharacters] = useState("林黛玉,贾宝玉");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [quota, setQuota] = useState<QuotaStatus | null>(null);

  async function refresh() {
    try {
      setBooks(await apiGet("/books"));
      setQuota(await apiGet<QuotaStatus>("/quota"));
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function createBook() {
    setBusy(true);
    setError("");
    try {
      const book = await apiPost<{ id: string }>("/books", {
        title: title || "未命名书卷",
        source: "upload",
        content,
      });
      setMessage(`已创建书卷 ${book.id}，开始蒸馏…`);
      const names = characters
        .split(/[,，、\s]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      const job = await apiPost<{ id: string; stage: string; book_id: string }>(
        `/books/${book.id}/distill`,
        { characters: names }
      );
      // 轮询蒸馏进度
      for (let i = 0; i < 30; i++) {
        const cur = await apiGet<{ stage: string; progress: Record<string, unknown> }>(
          `/books/${job.book_id}/distill-jobs/${job.id}`
        );
        const step = String((cur.progress as { step?: string })?.step || cur.stage);
        setMessage(`蒸馏中… ${cur.stage} / ${step}`);
        if (cur.stage === "done" || cur.stage === "failed") {
          setMessage(cur.stage === "done" ? "蒸馏完成" : "蒸馏失败");
          break;
        }
        await new Promise((r) => setTimeout(r, 400));
      }
      setTitle("");
      setContent("");
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid">
      <section className="card">
        <h3>新建书卷并蒸馏</h3>
        <p className="muted">
          粘贴原文片段 → 蒸馏人物包与关系 → 进入剧场。
          {quota && (
            <>
              {" "}
              配额：蒸馏 {quota.distill_used}/{quota.distill_limit}
            </>
          )}
        </p>
        <label>标题</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="红楼梦" />
        <label>人物（逗号分隔）</label>
        <input value={characters} onChange={(e) => setCharacters(e.target.value)} />
        <label>原文</label>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="把小说片段粘贴到这里…"
        />
        <div className="row" style={{ marginTop: 12 }}>
          <button onClick={createBook} disabled={busy}>
            {busy ? "处理中…" : "创建并蒸馏"}
          </button>
          {message && <span className="status-ok">{message}</span>}
          {error && <span className="status-bad">{error}</span>}
        </div>
      </section>

      <section>
        <h3 style={{ margin: "8px 0" }}>书卷列表</h3>
        <div className="grid books">
          {books.map((book) => (
            <article key={book.id} className="card">
              <h3>{book.title}</h3>
              <p className="muted">
                状态：{book.status} · {book.id}
              </p>
              <div className="row">
                <a className="button" href={`/books/${book.id}`}>
                  打开
                </a>
              </div>
            </article>
          ))}
          {!books.length && <p className="muted">还没有书卷，先创建一本。</p>}
        </div>
      </section>
    </div>
  );
}
