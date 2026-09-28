# 造梦空间 DreamSpace

基于 [造梦](zaomeng/) 人物智能的 Web 故事剧场。

- 设计文档：[DESIGN.md](DESIGN.md)
- 新功能计划：[docs/feature-plan-v0.3.md](docs/feature-plan-v0.3.md)
- 架构决策：[docs/adr/](docs/adr/)
- 契约测试清单：[docs/contract-tests.md](docs/contract-tests.md)

## 功能一览

- 书卷上传 / 蒸馏人物包与关系 / 导入导出 `.zaomeng.zip`
- 剧场多角色 SSE 对话、导演四项、场景卡
- 分支时间线、长期记忆、世界记忆（锁定事实）
- 章节归档、改写 diff、续写
- 名场面卡片分享、只读分享链接
- 跨作品群英会、协作席位、人物演进
- 匿名配额、桥接本机造梦、SQLite 持久化

## 快速开始

先获取造梦契约与 skill 来源：

```powershell
git clone https://github.com/wkbin/zaomeng zaomeng
```

### API

```powershell
cd services/api
uv sync --extra dev
uv run pytest tests -q
uv run uvicorn app.main:app --reload
```

测试时建议：

```powershell
$env:DREAMSPACE_STORE='memory'
$env:DREAMSPACE_SYNC_DISTILL='1'
```

### Web

```powershell
cd apps/web
npm install
npm run dev
```

打开 http://127.0.0.1:3000 。

### Docker

```powershell
docker compose up --build
```

## 目录

| 路径 | 说明 |
| --- | --- |
| `apps/web/` | Next.js 剧场 UI（剧场/章节/群英会/分享/桥接） |
| `services/api/` | FastAPI + 造梦 skill 适配 + SQLite 存储 |
| `zaomeng/` | 造梦仓库（人物包/关系/对话契约来源） |
| `docs/` | ADR、契约与功能计划 |

## 配置

复制 `.env.example` 为 `services/api/.env`：

| 变量 | 说明 |
| --- | --- |
| `DREAMSPACE_LLM_*` | OpenAI 兼容模型；未配置时走 Mock |
| `DREAMSPACE_STORE` | `sql`（默认，SQLAlchemy）/ `sqlite` / `memory` |
| `DREAMSPACE_DATABASE_URL` | 如 `postgresql+psycopg://...`；默认 SQLite 文件 |
| `DREAMSPACE_DB_PATH` | SQLite 路径，默认 `data/dreamspace.db` |
| `DREAMSPACE_SYNC_DISTILL` | `1` 时蒸馏同步执行（测试用） |

数据默认落 `services/api/data/dreamspace.db`，重启不丢书卷与会话。
