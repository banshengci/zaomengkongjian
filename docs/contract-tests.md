# 契约测试清单

> 目的：锁定与造梦（`vendor/zaomeng`）之间的数据/协议边界。升级 submodule 或改适配层前必须跑绿。
>
> 实现位置：`services/api/tests/contract/`（M1 起逐步补齐）

## 1. 人物档案 `PROFILE`

| ID | 断言 | 对应造梦来源 |
| --- | --- | --- |
| C-P-01 | 能解析标准 `# PROFILE` markdown，含 `## Meta` 且 `name` 非空 | `zaomeng-skill/references/output_schema.md` |
| C-P-02 | 关键分组存在：Meta / Basic Positioning / Root Layer / Inner Core / Voice / Evidence | 同上 |
| C-P-03 | `values.*` 均为 0–10 整数（存在该字段时） | 统一标尺 |
| C-P-04 | 列表字段分隔符为中文分号 `；`（core_traits 等） | 易混字段收紧定义 |
| C-P-05 | 无稳定证据的高风险字段允许为空，禁止占位词 | 原作优先原则 |
| C-P-06 | `evidence_source` 只含真实证据 ID，不复制原文 | Evidence 规则 |

## 2. 关系图 `RELATION_GRAPH`

| ID | 断言 | 来源 |
| --- | --- | --- |
| C-R-01 | 可解析 pair 段落；`pair_key` 形如 `A_B` 或文档约定分隔 | `sample_relations.md` |
| C-R-02 | `trust / affection / power_gap / conflict_point` 可读 | 同上 |
| C-R-03 | 数值字段边界符合造梦约定（存在则合法） | skill 校验 |

## 3. 对话协议（NDJSON + SSE）

| ID | 断言 | 来源 |
| --- | --- | --- |
| C-D-01 | NDJSON 每行是完整对象，含非空 `speaker` 与 `message` | `docs/architecture.md` |
| C-D-02 | 可选 `inner_thought`；未知字段不致解析失败 | 同上 |
| C-D-03 | SSE 事件名集合 ⊆ `{status,delta,reset,complete,error}` | `docs/server-api.md` |
| C-D-04 | `delta` 含 `index,speaker,role,field,text` | 同上 |
| C-D-05 | `complete` 含 `session`；`include_transcript=false` 时含 `appended_transcript` | 同上 |
| C-D-06 | 对话请求不得声明 `response_format=json_object` | NDJSON 协议约束 |
| C-D-07 | speaker 白名单校验失败不得用纯文本兜底掩盖 | 完成标准 |

## 4. 书卷包 `package_manifest.json`

| ID | 断言 | 来源 |
| --- | --- | --- |
| C-K-01 | 支持 `schema_version` 0 与 1；未知版本拒绝 | `docs/data-dictionary.md` |
| C-K-02 | v0 缺字段按规则归一（status_text / graph_status / builtin / character_count） | 兼容冻结规则 |
| C-K-03 | 导入解压前先校验 manifest | 运行时契约 |
| C-K-04 | 导出包不写入宿主绝对路径 | 运行时契约禁止事项 |

## 5. 扩展字段

| ID | 断言 |
| --- | --- |
| C-X-01 | 所有产品扩展键以 `x_dreamspace_` 开头 |
| C-X-02 | 导入/导出造梦包时可丢弃扩展字段而不失败 |
| C-X-03 | 导出回造梦格式时不污染 canonical 键名 |

## 6. 安全边界

| ID | 断言 |
| --- | --- |
| C-S-01 | 模型 API Key 不出现在 manifest、日志、分享投影、诊断导出 |
| C-S-02 | 分享投影只读：无输入/写入端点 |
| C-S-03 | 日志含文本时截断，且不含完整原文/完整 prompt |

## 执行方式（M1 落地）

```powershell
cd services/api
uv run pytest tests/contract -q
```

失败即视为契约破坏，不得合并。
