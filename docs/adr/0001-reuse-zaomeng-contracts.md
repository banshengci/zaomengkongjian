# ADR-0001：产品层复用造梦契约，不平行造 schema

## 状态

已接受

## 背景

造梦已稳定定义人物档案 `PROFILE`、关系图 `RELATION_GRAPH`、对话 NDJSON 协议、书卷包 `package_manifest.json`。造梦空间是产品层，若私造平行字段会导致蒸馏产物无法互通、桥接模式无法落地。

## 决策

1. 人物、关系、对话事件、书卷包 **直接采用造梦 canonical 定义**。
2. 造梦空间新增产品字段走扩展命名空间 `x_dreamspace_*`，禁止改写 canonical 键名。
3. `vendor/zaomeng` 以 git submodule 钉住 tag；适配层是唯一允许读 skill 工具路径的地方。
4. 契约测试锁定关键字段清单，升级 submodule 时必须跑绿。

## 后果

- 正面：可导入/导出 `.zaomeng.zip`，桥接本机造梦成本低，社区书卷包可直接用。
- 负面：造梦 schema 变更会波及本产品；需契约测试与适配层隔离。
- 备选（已否决）：内部自有 schema + 双向转换器 —— 转换面过大，长期漂移风险高。
