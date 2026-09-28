export const API_BASE =
  process.env.NEXT_PUBLIC_DREAMSPACE_API || "http://127.0.0.1:8000/api/v1";

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export type Book = {
  id: string;
  title: string;
  status: string;
  novel_id: string;
};

export type Character = {
  id: string;
  name: string;
  role_tags: string[];
  profile?: Record<string, unknown>;
  evolution_log?: { fields: Record<string, string>; note: string; at: string }[];
};

export type Relation = {
  pair_key: string;
  trust: number;
  affection: number;
  conflict_point: string;
};

export type Session = {
  id: string;
  book_id: string;
  title: string;
  mode: string;
  participants: string[];
  transcript_count: number;
  branch_of?: string;
  branch_label?: string;
  is_mainline?: boolean;
};

export type SessionTreeNode = {
  id: string;
  title: string;
  branch_of: string;
  branch_label: string;
  is_mainline: boolean;
  transcript_count: number;
  children: SessionTreeNode[];
};

export type TurnMessage = {
  speaker: string;
  message: string;
  role: string;
  inner_thought?: string;
};

export type Turn = {
  id: string;
  status: string;
  messages: TurnMessage[];
};

export type MemoryItem = {
  id: string;
  text: string;
  category: string;
  pinned: boolean;
  enabled: boolean;
  status: string;
};

export type WorldFact = {
  id: string;
  summary: string;
  location: string;
  time_hint: string;
  locked: boolean;
  active: boolean;
};

export type WorldView = {
  facts: WorldFact[];
  timeline: {
    time_hint: string;
    location: string;
    summary: string;
    locked: boolean;
  }[];
};

export type Chapter = {
  id: string;
  title: string;
  content_md: string;
  revisions?: { content: string; instruction: string }[];
};

export type SessionMember = {
  user_id: string;
  display_name: string;
  character: string;
  role: string;
};

export type HighlightCard = {
  id: string;
  title: string;
  lines: TurnMessage[];
  share_token: string;
};

export type QuotaStatus = {
  user_id: string;
  distill_used: number;
  distill_limit: number;
  turn_used: number;
  turn_limit: number;
};
