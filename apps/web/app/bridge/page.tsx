"use client";

import { useState } from "react";
import { apiGet, apiPost, type QuotaStatus } from "@/lib/api";

export default function BridgePage() {
  const [baseUrl, setBaseUrl] = useState("http://127.0.0.1:0");
  const [token, setToken] = useState("");
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [quota, setQuota] = useState<QuotaStatus | null>(null);

  async function ping() {
    setError("");
    setResult("");
    try {
      const data = await apiPost("/bridge/health", { base_url: baseUrl, token });
      setResult(JSON.stringify(data, null, 2));
    } catch (e) {
      setError(String(e));
    }
  }

  async function sync() {
    setError("");
    setResult("");
    try {
      const data = await apiPost("/bridge/sync", { base_url: baseUrl, token });
      setResult(JSON.stringify(data, null, 2));
    } catch (e) {
      setError(String(e));
    }
  }

  async function loadQuota() {
    try {
      const data = await apiGet<QuotaStatus>("/quota");
      setQuota(data);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <section className="card" style={{ maxWidth: 680 }}>
      <h3>桥接本机造梦</h3>
      <p className="muted">
        仅允许 127.0.0.1 / localhost。可将本机书卷只读镜像到 Web。
      </p>
      <label>本地地址</label>
      <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
      <label>Bearer Token</label>
      <input
        value={token}
        onChange={(e) => setToken(e.target.value)}
        placeholder="dev-token"
      />
      <div className="row" style={{ marginTop: 14 }}>
        <button onClick={ping}>测试连接</button>
        <button className="secondary" onClick={sync}>
          同步书卷
        </button>
        <button className="secondary" onClick={loadQuota}>
          查看配额
        </button>
        {error && <span className="status-bad">{error}</span>}
      </div>
      {quota && (
        <p className="muted">
          蒸馏 {quota.distill_used}/{quota.distill_limit} · 回合 {quota.turn_used}/
          {quota.turn_limit}
        </p>
      )}
      {result && (
        <pre className="muted" style={{ whiteSpace: "pre-wrap" }}>
          {result}
        </pre>
      )}
    </section>
  );
}
