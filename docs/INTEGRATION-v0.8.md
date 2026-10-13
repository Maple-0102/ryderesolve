# Judge / Orchestration v0.8 · 2026-10-13

本轮新增规则来源说明、通用提示词、可复现模拟评估包、评估指标及一次补材料重跑。
EvidenceTools 原代码与其 Evidence / Advocate 核心 schema 未修改。

## Judge 通用提示词

移除固定的 DISP-002 时间数值和 SYN-ROUTE-001 缺证据提示，具体案情仅从本次案卷与审计结果读取。
保留未解决的政策缺口阻止裁决、事实/陈述区别、金额与责任依据检查。仍然是规则辅助的 Judge，并非模型自行发现所有数据问题。

## 规则来源

`calculations.policy_provenance` 包括每条政策的 ID、来源标签、源数据路径、团队程序检查和版本哈希。
来源标签继承 Evidence audit；不做独立真实性认证，不把团队实现约定提升为官方收费规则。
页面增加“规则来源”。这是编排层计算元数据，不要求 Advocate 修改现有输出结构。

## 非事实请求

`schemas/judge-analysis.schema.json` 的 `argument_assessments.assessment` 增加 `not_factual_claim`。

- 适用于程序性请求、试图让裁判执行指令的文本；仍逐条保留并解释。
- 支持与反驳证据必须为空，政策引用可说明程序依据。
- 不得把到达、交通、金额、乘客同意等实质主张藏进此类型。
- 双方总评仅统计事实主张；仅有非事实请求的一方必须 unresolved。
- 决定责任所需的条件和证据检查独立保留，该类型不能使关键缺口消失。

类型选择仍依赖语义判断，程序并不能证明自由文本被分类正确。

## 一次补材料重跑

```python
result = orchestrator.rerun_with_supplement(
    previous_result,
    new_snapshot,
    source_note="补充资料的来源、取得方式和限制",
)
```

调用前准备新的完整 Evidence 快照；必须与原案同 case_id，有源数据变化并通过快照重建校验。
只允许从待复核案件补充一次；没有材料变化、缺少说明或连续第二次补充都会被拒绝。
整个编排重新执行，双方开场及回应均按新快照重新生成，旧快照 JSON Advocate 被拒绝。
旧裁决不加入新 Judge 输入，结果保存旧/新快照与父运行关联；页面显示补充来源及前后建议。

此 API 不会搜索或编造材料，也不独立认证提供者身份。不是已接入生产 Evidence 的自动补证服务。
`outputs/supplement-v0.8/` 是离线流程演示，Judge / Advocate 都仍离线，不证明补材料后真实模型会改判。

## 模拟评估包

`outputs/judge-dataset-v0.8/`：9 个开发题、6 个留出候选题。
新增题改变费用差额（SGD 2 / 8）、核实条件及冲突，保持叙述与价格数据一致。
`input-*.json` 仅包含系统消息和案卷消息，`scorer-only-labels.json` 仅供评分，禁止发送给模型。
`manifest.json` 保存输入 SHA256、快照和来源标签，可重新生成并核对。

所有预期判断是团队规则下的人工测试目标，不是 Ryde 官方标准答案。
只有两个种子案例家族，留出候选与开发题共享路线来源；不能推断独立真实业务准确率。
全额退款业务场景未覆盖，报告明确列为 0/0。开发题上修改过提示词，因此开发分数不是独立泛化评估。

## 评估报告

保存每题输入哈希、规则来源哈希、裁决/金额、完整被拒绝输出（非法 JSON 时安全省略）、错误码、耗时和记录到的用量。
按预期裁决分类计分，单列无效输出、错误转人工、错误明确裁决、金额错误以及顺序对照。
每完成一题输出进度并保存 `.partial.json`，断线或中断后仍能核对已完成部分；不自动重试。
模型 confidence 仍是未经校准的自评。token 合计不是账单，不根据测试分数宣称线上准确率。

## 尚未完成

真实 Advocate 接入、补证来源服务、最终完整多 Agent 联调、独立人工审阅、全额退款业务样例及官方政策缺口确认。
未新增第二个 LLM 审查 Agent。未同步或发布腾讯 ADP 云端应用；本地新提示词不代表云应用已更新。

本轮每题每个提示版本只调用一次。顺序对照同时受模型随机性影响，不能仅凭一次一致性结果宣称公平。

## 推理档位与精简输出

VertexConfig 增加可选 thinking_level；支持 LOW / MEDIUM / HIGH，未配置时保留提供商默认。
通过 `--thinking-level LOW` 或 `RYDE_VERTEX_THINKING_LEVEL` 显式选择，并在 transport 中记录档位及输出上限。
不使用 Gemini 3 已弃用的 thinkingBudget，不自动重试超时或截断请求。

转人工时不重复输出 findings，原因和证据在 case_analysis 内保留；明确裁决时只输出有完整条件依据的责任推断。
这是减少重复表达和错误分类的输出约定，未放宽任何责任、金额或证据检查。

官方参数来源（2026-10-13核对）：
- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/thinking
- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1/GenerationConfig

LOW与默认档位的报告独立保存。开发题被用于修改提示词，结果不是未见过数据的准确率测量。

## 金额标签明确化

`calculations.decision_amount_rules` 给出记录收费总额与已记录的路线差额上限。
全额退款指退全部记录收费；保留原始报价、只退额外费用仍为部分退款。这是团队接口金额定义。
原始9题中该题失败已保留；修正后专项复测通过，未将两版结果合并成9/9。
