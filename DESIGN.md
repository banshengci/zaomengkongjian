# 造梦空间（DreamSpace）设计文档

> 版本：v0.2（M1–M5 已落地）  
> 日期：2026-08-12  
> 状态：设计 + 实现对照

---

## 1. 一句话定位

**造梦空间**是建立在造梦（zaomeng）人物智能之上的 **Web 故事剧场**：把小说蒸馏出的人物包、关系图谱与多角色对话能力，做成浏览器里可创建、可扮演、可分享的故事空间。

---

## 2. 目标用户

| 用户 | 核心诉求 |
| --- | --- |
| 读者 / 同人玩家 | 和角色对话、围观群聊、改编结局 |
| 写手 / 二创作者 | 用人物包推演情节、试对话、攒章节 |
| 分享者 | 把名场面或关系发给朋友 |
| 桌面造梦用户 | 浏览器继续本机故事（桥接模式） |

---

## 3. 与造梦的关系

- **契约对齐**：PROFILE / RELATION_GRAPH / NDJSON / package_manifest 直接采用造梦定义（ADR-0001）。
- **skill 复用**：蒸馏走 `zaomeng-skill` 工具链（ADR-0003）。
- **模式 A 独立**（默认）：自带 LLM，mock 可跑通。
- **模式 B 桥接**：`POST /api/v1/bridge/*` 仅访问 localhost。
- **模式 C 包导入**：`POST /api/v1/books/import`。

---

## 4. 已实现功能（对照 MVP）

| 模块 | 状态 | 入口 |
| --- | --- | --- |
| 书卷创建/上传/列表/删除 | ✅ | `POST /api/v1/books` |
| 蒸馏人物 + 关系 | ✅ | `POST /api/v1/books/{id}/distill` |
| 人物档案查看/字段补丁 | ✅ | `GET/PUT /api/v1/books/{id}/personas/{name}` |
| 关系列表/更新 | ✅ | `GET /api/v1/books/{id}/relations`、`PATCH .../relations/{pair_key}` |
| 书卷包导入 | ✅ | `POST /api/v1/books/import` |
| 剧场会话 + 回合 | ✅ | `POST /api/v1/theater/sessions`、`.../turns` |
| SSE 流式对话 | ✅ | `POST .../reply/stream` |
| 场景卡 | ✅ | 内置 seed + store |
| 导演四项 | ✅ | `POST .../director` |
| 章节归档/导出 | ✅ | `POST .../archive`、`GET .../chapters/{id}/export` |
| 只读分享 | ✅ | `POST /api/v1/theater/share` |
| 模型设置 | ✅ | `/api/v1/settings/model` |
| 桥接本机造梦 | ✅ | `/api/v1/bridge/*` |
| Web 剧场 UI | ✅ | `apps/web` |
| Docker Compose | ✅ | 根目录 `docker-compose.yml` |

---

## 5. 系统架构（实现版）

```
Next.js (apps/web)
  └─ /api/v1/* rewrite → FastAPI (services/api)
        ├─ integrate/  造梦 skill 适配（唯一碰 vendor 路径）
        ├─ distill/    蒸馏编排
        ├─ llm/        OpenAI 兼容 + Mock
        ├─ store/      内存存储（可换 PG）
        └─ api/        books / personas / theater / settings / bridge
```

对话协议：模型 NDJSON → 应用 SSE（`status/delta/reset/complete/error`）。

---

## 6. 目录结构

```text
zaomengkongjian/
├── DESIGN.md / README.md / docker-compose.yml / .env.example
├── apps/web/                 # Next.js 剧场 UI
├── services/api/             # FastAPI
│   ├── app/{api,domain,distill,integrate,llm,store}
│   └── tests/contract/
├── docs/{adr,contract-tests.md}
└── zaomeng/                  # 造梦克隆（skill 来源）
```

---

## 7. 开放问题（已默认决策）

| 问题 | 默认 |
| --- | --- |
| 分享有效期 | 默认 72 小时，创建时可调 1h–30d |
| 匿名/登录 | v1 匿名可用，蒸馏不强制登录 |
| 剧场视觉 | 纸面剧场（深色舞台 + 台词气泡） |
| 桥接优先级 | 已做 health/runs/sessions 探测，完整同步后置 |

---

## 8. 里程碑状态

| 阶段 | 状态 |
| --- | --- |
| M0 设计冻结 | ✅ ADR + 契约清单 |
| M1 走通蒸馏 | ✅ 上传 → 人物包 + 关系 |
| M2 剧场 MVP | ✅ 会话 + SSE + 场景 + UI |
| M3 导演归档分享 | ✅ |
| M4 发布打磨 | ✅ 设置 + Docker + 观测骨架 |
| M5 桥接本机 | ✅ 基础探测接口 |

---

## 9. 验证

```powershell
cd services/api
uv run ruff check .
uv run pytest tests -q   # 16 passed
```

```powershell
# 本地开发
cd services/api && uv run uvicorn app.main:app --reload
cd apps/web && npm install && npm run dev
```

---

## 10. 后续

- 内存存储 → PostgreSQL + Redis worker
- 分享页登录墙 / 配额
- 完整书卷包导出、章节改写
- 桥接模式完整同步书卷与会话
