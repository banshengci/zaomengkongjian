"use client";

import { useState } from "react";
import { apiGet, apiPost, type SessionMember } from "@/lib/api";

export function EvolvePanel({
  bookId,
  character,
  sessionId,
}: {
  bookId: string;
  character: string;
  sessionId: string;
}) {
  const [focus, setFocus] = useState("信任变化");
  const [info, setInfo] = useState("");
  const [error, setError] = useState("");
  const [proposal, setProposal] = useState<{
    id: string;
    fields: Record<string, string>;
    rationale: string;
  } | null>(null);

  async function propose() {
    setError("");
    try {
      const data = await apiPost<{
        id: string;
        fields: Record<string, string>;
        rationale: string;
      }>(`/books/${bookId}/personas/${encodeURIComponent(character)}/evolve/proposal`, {
        session_id: sessionId,
        focus,
      });
      setProposal(data);
      setInfo(data.rationale);
    } catch (e) {
      setError(String(e));
    }
  }

  async function apply() {
    if (!proposal) return;
    try {
      await apiPost(
        `/books/${bookId}/personas/${encodeURIComponent(character)}/evolve/apply`,
        { proposal_id: proposal.id, note: "用户确认" }
      );
      setInfo("已应用到人物档案");
      setProposal(null);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <section className="card">
      <h3>人物演进 · {character}</h3>
      <div className="row">
        <input
          value={focus}
          onChange={(e) => setFocus(e.target.value)}
          placeholder="关注点"
        />
        <button className="secondary" onClick={propose}>
          生成提案
        </button>
      </div>
      {proposal && (
        <>
          <pre className="muted" style={{ whiteSpace: "pre-wrap" }}>
            {JSON.stringify(proposal.fields, null, 2)}
          </pre>
          <button onClick={apply}>应用提案</button>
        </>
      )}
      {info && <p className="muted">{info}</p>}
      {error && <p className="status-bad">{error}</p>}
    </section>
  );
}

export function SeatPanel({
  sessionId,
  participants,
}: {
  sessionId: string;
  participants: string[];
}) {
  const [members, setMembers] = useState<SessionMember[]>([]);
  const [character, setCharacter] = useState(participants[0] || "");
  const [name, setName] = useState("玩家");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  async function refresh() {
    try {
      setMembers(await apiGet<SessionMember[]>(`/theater/sessions/${sessionId}/members`));
    } catch (e) {
      setError(String(e));
    }
  }

  async function claim() {
    setError("");
    setInfo("");
    try {
      await apiPost(`/theater/sessions/${sessionId}/members`, {
        character,
        display_name: name,
      });
      setInfo(`已认领 ${character}`);
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <section className="card">
      <h3>协作席位</h3>
      <div className="row">
        <select value={character} onChange={(e) => setCharacter(e.target.value)}>
          {participants.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <input
          style={{ maxWidth: 120 }}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="显示名"
        />
        <button className="secondary" onClick={claim}>
          认领
        </button>
        <button className="secondary" onClick={refresh}>
          刷新
        </button>
      </div>
      <div style={{ marginTop: 8 }}>
        {members.map((m) => (
          <div key={`${m.user_id}-${m.character}`} className="chip" style={{ margin: 4 }}>
            {m.display_name} · {m.character} · {m.role}
          </div>
        ))}
      </div>
      {info && <p className="status-ok">{info}</p>}
      {error && <p className="status-bad">{error}</p>}
    </section>
  );
}
