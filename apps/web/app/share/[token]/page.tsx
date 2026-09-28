"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiGet } from "@/lib/api";

type SharePayload = {
  kind: string;
  readonly: boolean;
  title?: string;
  session?: { title: string; participants: string[] };
  transcript?: { speaker: string; message: string; role: string }[];
  chapter?: { title: string; content_md: string };
  lines?: { speaker: string; message: string; role: string }[];
};

export default function SharePage() {
  const params = useParams<{ token: string }>();
  const [data, setData] = useState<SharePayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet<SharePayload>(`/theater/share/${params.token}`)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [params.token]);

  if (error) return <p className="status-bad">{error}</p>;
  if (!data) return <p className="muted">加载中…</p>;

  return (
    <section className="card">
      <h3>
        {data.kind === "session"
          ? data.session?.title
          : data.kind === "highlight"
            ? `名场面 · ${data.title || ""}`
            : data.chapter?.title}
      </h3>
      <p className="muted">只读分享 · 造梦空间</p>
      {(data.kind === "session" || data.kind === "highlight") && (
        <div className="stage">
          {(data.kind === "highlight" ? data.lines || [] : data.transcript || []).map(
            (m, idx) => (
              <div
                key={idx}
                className={`bubble ${m.role === "narration" ? "narration" : "character"}`}
              >
                <div className="speaker">{m.speaker}</div>
                <div>{m.message}</div>
              </div>
            )
          )}
        </div>
      )}
      {data.kind === "chapter" && (
        <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>
          {data.chapter?.content_md}
        </pre>
      )}
    </section>
  );
}
