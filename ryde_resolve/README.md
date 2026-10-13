# Judge / Orchestration

本模块已由 mock 骨架升级为 EvidenceTools 集成版。请阅读仓库根目录 `README.md` 和 `docs/INTEGRATION-v0.5.md`。

主要入口：
- `evidence.py`：调用队友 prepare_case；校验完整快照，使用同一版本的输出 schema。
- `rule_engine.py`：展示队友 audit 中的计算，不自行认定计费起点。
- `agents.py`：Advocate JSON 回放、Judge HTTP 调用与提示词拼装。
- `orchestrator.py`：一轮陈述 + 一轮对称回应 + Judge + 校验/复核。
- `mock_agents.py`：有明确标签的离线占位和复核输出，无写死收费判定。
- `contracts.py`：调用队友 schema 后做本地暂定业务检查。
- `review_policy.py`：版本化复核问题分类，未知问题保守处理。
- `reasoning_checks.py`：证据类型、双方分析与复核回答校验；不是自然语言正确性证明。
- `deliberation.py`：逐条论点、裁决条件、结论依赖关系检查。
- `handoff.py`：根据复核原因生成建议交接单。
- `ui.py`：生成双案例 HTML 和证据原文锚点。
- `run_demo.py`：命令行入口，默认离线。
