# ADR-0004：人物包与关系以文档存储，DB 只存引用

## 状态

已接受

## 背景

`PROFILE` 含 50+ 语义字段（含 evidence、arc、voice 细则），拍平进关系库会形成脆弱宽表，且与造梦 markdown canonical 形态不一致。

## 决策

1. `PROFILE.generated.md`、关系图 JSON/Mermaid 原样存对象存储/本地卷，DB 记录 `character.profile_ref` 等引用。
2. 列表/检索所需少量标量（name、novel_id、role_tags、头像版本）冗余到 DB 投影列。
3. 导入 `.zaomeng.zip` 时按 package_manifest 校验，缺 graph/payload 允许降级导入。
4. 删除书卷级联删除文件与衍生会话。

## 后果

- 正面：与造梦包格式互认；字段演进不必迁库。
- 负面：跨字段查询需读文件；缓存与索引要自己管。
- 备选（已否决）：EAV/JSONB 全量入库 —— 校验与导出仍要回写 canonical 形态，收益有限。
