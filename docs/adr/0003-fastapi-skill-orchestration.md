# ADR-0003：FastAPI 复用 zaomeng-skill 做蒸馏编排

## 状态

已接受

## 背景

`zaomeng-skill` 提供 distill / materialize / export_graph 等 Python 工具与提示词，蒸馏产物即标准人物包。造梦空间上传原文后要产出同一套产物，不应重写蒸馏逻辑。

## 决策

1. 服务端 **BFF/API 选 FastAPI + Python 3.12**，便于直接调用 skill 工具函数。
2. 通过 `services/api/app/integrate/` 适配层封装 skill 入口（路径解析、run_manifest、错误翻译），业务代码禁止散落 `subprocess` 拼路径。
3. 蒸馏是分钟级长任务：入队执行（Redis + worker），API 只返回 job 状态；进度对齐 skill 的 `run_manifest.progress`。
4. LLM 密钥只在服务端加密存储，喂给适配层，不写入 manifest / 日志 / 分享包。

## 后果

- 正面：蒸馏质量与造梦一致；提示词与 schema 单点维护。
- 负面：Python 服务依赖 skill 目录布局；skill 大改需改适配层。
- 备选（已否决）：在 Node/Go 重写蒸馏 —— 重复建设且提示词/校验易漂移。
