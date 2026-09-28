"use client";

import type { SessionTreeNode } from "@/lib/api";

function NodeView({
  node,
  depth,
  activeId,
  onPick,
}: {
  node: SessionTreeNode;
  depth: number;
  activeId: string;
  onPick: (id: string) => void;
}) {
  const isActive = node.id === activeId;
  return (
    <div style={{ marginLeft: depth * 18 }}>
      <button
        type="button"
        onClick={() => onPick(node.id)}
        style={{
          display: "block",
          width: "100%",
          textAlign: "left",
          background: isActive ? "#243552" : "transparent",
          color: node.is_mainline ? "var(--ink)" : "var(--muted)",
          border: `1px solid ${isActive ? "var(--accent)" : "var(--line)"}`,
          borderRadius: 10,
          padding: "8px 10px",
          marginBottom: 6,
          cursor: "pointer",
        }}
      >
        <div style={{ fontWeight: 600 }}>
          {node.is_mainline ? "主线" : "支线"} · {node.title}
        </div>
        <div className="muted" style={{ fontSize: "0.82rem" }}>
          {node.branch_label || "—"} · {node.transcript_count} 条
        </div>
      </button>
      {node.children.map((child) => (
        <NodeView
          key={child.id}
          node={child}
          depth={depth + 1}
          activeId={activeId}
          onPick={onPick}
        />
      ))}
    </div>
  );
}

export default function BranchTimeline({
  tree,
  activeId,
  onPick,
  onBranch,
  busy,
}: {
  tree: SessionTreeNode[];
  activeId: string;
  onPick: (id: string) => void;
  onBranch: (label: string) => void;
  busy?: boolean;
}) {
  return (
    <section className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h3 style={{ margin: 0 }}>分支时间线</h3>
        <button
          className="secondary"
          disabled={busy || !activeId}
          onClick={() => {
            const label = window.prompt("分支标签", "如果当时没有离开");
            if (label) onBranch(label);
          }}
        >
          开支线
        </button>
      </div>
      <p className="muted">从当前节点分出 if 线，对照不同走向。</p>
      {tree.length === 0 && <p className="muted">暂无会话。</p>}
      {tree.map((node) => (
        <NodeView
          key={node.id}
          node={node}
          depth={0}
          activeId={activeId}
          onPick={onPick}
        />
      ))}
    </section>
  );
}
