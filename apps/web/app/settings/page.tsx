"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPut, apiPost } from "@/lib/api";

export default function SettingsPage() {
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [configured, setConfigured] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    apiGet<{ model: string; base_url: string; api_key_configured: boolean }>(
      "/settings/model"
    )
      .then((data) => {
        setModel(data.model || "");
        setBaseUrl(data.base_url || "");
        setConfigured(data.api_key_configured);
      })
      .catch((e) => setError(String(e)));
  }, []);

  async function save() {
    try {
      const data = await apiPut("/settings/model", {
        provider: "openai-compatible",
        model,
        base_url: baseUrl,
        api_key: apiKey,
        max_tokens: 4096,
      });
      setConfigured(
        Boolean((data as { api_key_configured?: boolean }).api_key_configured)
      );
      setMessage("已保存");
      setApiKey("");
    } catch (e) {
      setError(String(e));
    }
  }

  async function test() {
    setTesting(true);
    setError("");
    setMessage("");
    try {
      const result = await apiPost<{ ok: boolean; latency_ms: number; message: string }>(
        "/settings/model/test",
        {
          provider: "openai-compatible",
          model,
          base_url: baseUrl,
          api_key: apiKey,
          max_tokens: 64,
        }
      );
      setMessage(
        result.ok
          ? `连接成功 · ${result.latency_ms}ms`
          : `连接失败：${result.message}`
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setTesting(false);
    }
  }

  return (
    <section className="card" style={{ maxWidth: 640 }}>
      <h3>模型设置</h3>
      <p className="muted">
        OpenAI 兼容端点。密钥仅保存在服务端，不会出现在响应里。
      </p>
      <label>模型</label>
      <input
        value={model}
        onChange={(e) => setModel(e.target.value)}
        placeholder="gpt-4o-mini"
      />
      <label>Base URL</label>
      <input
        value={baseUrl}
        onChange={(e) => setBaseUrl(e.target.value)}
        placeholder="https://api.openai.com/v1"
      />
      <label>API Key {configured && "（已配置，可留空）"}</label>
      <input
        type="password"
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        placeholder="sk-..."
      />
      <div className="row" style={{ marginTop: 14 }}>
        <button onClick={save}>保存</button>
        <button className="secondary" onClick={test} disabled={testing}>
          {testing ? "测试中…" : "测试连接"}
        </button>
        {message && <span className={message.includes("成功") ? "status-ok" : "status-bad"}>{message}</span>}
        {error && <span className="status-bad">{error}</span>}
      </div>
    </section>
  );
}
