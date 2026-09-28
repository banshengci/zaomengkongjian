# 造梦空间 API

建立在造梦（zaomeng）人物智能之上的故事剧场服务。设计见根目录 [`DESIGN.md`](../../DESIGN.md)。

## 开发

```powershell
cd services/api
uv sync --extra dev
uv run pytest tests -q
uv run ruff check .
uv run pyright app tests
uv run uvicorn app.main:app --reload
```

## 结构

- `app/integrate/` — 造梦契约与 skill 适配（唯一允许碰 `zaomeng/zaomeng-skill` 的地方）
- `app/distill/` — 蒸馏编排
- `app/store/` — M1 内存存储，后续换 PostgreSQL
- `tests/contract/` — 契约测试，见 `docs/contract-tests.md`
