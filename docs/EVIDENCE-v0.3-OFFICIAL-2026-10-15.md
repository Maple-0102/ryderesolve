# 官方数据与政策接入 · 2026-10-15

琪琪负责 Evidence/Data + tools。本分支基于小组仓库 `Maple-0102/ryderesolve` 的 `2e6bea7`，保留队友的 Advocate、Judge、编排和 UI，只做官方数据接入、规则同步与必要的兼容修复。没有向旧个人仓库推送，也没有执行退款、发群消息或提交比赛作品。

## 输入与来源

四份用户提供的官方附件原样归档在 `vendor/ryderesolve-evidence-tools/sources/official/2026-10-15/`。`manifest.json` 记录原文件名、文件字节哈希、JSON 语义哈希和明确的投影排除路径。它们是主办方提供的样例，不声称是真实运营记录或已经独立核验的数据。

| 案例 | 运行时处理 | 确定性结果与边界 |
| --- | --- | --- |
| DISP-001 / route_deviation | 保留原档；运行时排除答案及编辑性裁决分析，保留证据原值和数组索引 | 报告距离 24.8−20.5=4.3 km；总票价差 650 分；原记录的超出距离费用 344 分。三个数含义不同。 |
| DISP-002 / no_show_charge | JSON 与旧版完全一致；单独补充政策文档 | 订单计时 480 秒、App 计时 470 秒、预约到取消 360 秒均保留。 |
| DISP-003 / fare_dispute | JSON 原值完整保留 | 实收 1650 分、报价 1200 分、差额 450 分；所给费用构成与 surge-only 差额一致。未授予退款。 |
| SYN-ROUTE-001 | 保留 synthetic 及自设规则标签，不套用官方文档 | 继续用于旧合成接口回归，不冒充新增官方案例。 |

DISP-001 的 `case_metadata`、`recommended_ruling`、`evidence_summary`、`chat_log_analysis`、`traffic_analysis` 等含答案或编辑性分析。所有排除字段的完整路径见 manifest；其中也排除了费用说明与一条交通描述中的裁决性文字。原附件仍完整保存，可逐项复现投影。原档不进入安装 wheel，runtime 不加载它；不要把原档、旧评估标签或整个仓库交给 Agent 当案卷。政策第 7 节的历史先例属于政策原文，可以引用，但不是当前案卷答案。

## DISP-002 等待时间：已经明确与仍然缺失的部分

- v2.1 **§2.1 明确从 scheduled pickup time 起算五分钟免费等待**。本案预约 08:45，免费期结束 08:50，取消 08:51，预约到取消为 6 分钟。司机 08:43 到达不提前启动该条规定的免费等待。
- 案例内 `cancellation_policy.no_show_threshold_min=8` 仍保留。独立政策没有定义这个额外八分钟门槛从哪里开始，也没有说明它与“免费等待后可取消”的五分钟条款如何衔接，或哪份来源覆盖哪份。
- 因此新增 `NO_SHOW_THRESHOLD_CLOCK_UNSPECIFIED` 与 `POLICY_SOURCE_CONFLICT`；不得把 5 和 8 相加为 13，不得选有利于某方的计时起点，也不得声称已充分证明收费正确。
- 原订单/App 起点差异和提前到达记录保留为信息提示；已不能笼统地说“官方完全没有免费等待起算规则”。独立文档未提供时仍保留原 `POLICY_CLOCK_BASIS_UNSPECIFIED` 缺失标记。
- §2.3 的联系义务为 **至少一条 App 消息 AND 至少一次 App 电话**；未接听仍是一次尝试。§6.3 的历史 fraud flag 触发 95% 置信度门槛，不能用来证明本次责任。

2026-10-15 按用户授权查看了 Digital Native 官方 WhatsApp 群的四份资料发布上下文，并检索 policy、wait、no-show。所查看消息未见明确的替代/优先级说明；这是有限的可见历史核查，不是对所有历史记录均不存在说明的保证。未把群成员号码、邀请链接或私人聊天复制进仓库。仍需主办方澄清上述两个缺口。

## 新数据的政策与事实边界

DISP-001：政策 §1.2 区分改道理由、及时通知和乘客同意；§1.4 要求历史交通 API 依据。样例交通记录不冒充本次真实 API 调用，也没有补造口头通知录音。政策阈值使用报告的道路路线距离，不能用稀疏 GPS 折线替代。**4.3 km > 2 km，§6.2 要求转人工**；即使可讨论超出距离费用，也不能按样例推荐直接自动裁决。

DISP-003：新增 surge 日志、`message` 聊天格式与嵌套费用构成映射；按 Decimal 算钱，保留版本一致的来源引用。`rider_notified=false` 是日志记录的否定值，日志缺失则为 unknown，不能当成未通知。检查费用合计、差额、surge multiplier、通知时点及通知细节之间的冲突。Booking fee 不加入 surge；这里只核对现有 subtotal/total，未虚构原文没有列出的逐项资费。

所有金额按新加坡样例上下文解释为 SGD；新样例的 fare 字段未单独编码币种，审计会注明这个解释来源。团队既有 `refund_full` 指全额退整笔扣款；若退 4.50 差价而保留 12.00 原报价，应使用 `refund_partial`，不是把政策“full surge differential”误映射成整单全退。

按随案政策暴露类别、金额与 fraud 置信度约束；安全指示仅生成证据准备和人工复核要求，不作责任裁决。关键词筛查只是补充保护，不是完整安全分类器。新增官方案卷的真实模型判决质量、完整公平性与抗提示注入能力未在本轮验证。

## 接口兼容与队友接入

`case_id / evidence_id / evidence_refs / policy_refs / decision`、facts/claims/findings 的原有必填字段及嵌套均不改名。Evidence/Advocate 两份 Evidence Pack schema 同步新增 `fare_dispute` 枚举。Advocate 通用提示同步 v2.1 的条件式解释规则；不存在随案政策时不凭提示词制造官方依据。

```python
from ryderesolve_evidence import EvidenceTools
tools = EvidenceTools()
snapshot = tools.prepare_case("DISP-003")
pack = snapshot["evidence_pack"]
# 将同一 pack/audit 交给双方 Agent；保存 snapshot_id。
policy = tools.get_policy("DISP-003", "P-RYDE-2.1-S3.3",
                          expected_snapshot_id=snapshot["snapshot_id"])
```

- `prepare_case` 旁路新增 `policy_documents`，不改变原 `raw`。新文档的完整内容与来源信息纳入 snapshot_id；原始案例 SHA 不变也可能获得新快照，必须重跑下游输出。
- 旧 `P-001` 等案内规则编号保留；文档规则使用 `P-RYDE-2.1-S2.1` 等编号。旧 DISP-002 的 E-001…E-038 保持含义，仅追加政策计算事实。
- `source_index.policy[].source_document_id` 表示该条 source_refs 在哪个政策文档内解析；无此字段时继续指向 raw。请用 `get_policy` 的 excerpts 或 `policies.source_value`，不要一律对 raw 解引用。团队 snapshot verifier、规则来源表、UI 已接入。
- 包级 `normalize_evidence(raw)` 不会偷偷加载文档。需要官方政策请调用 `prepare_case` / tools.normalize_evidence；自定义来源可用 `build_bundle(raw, metadata, policy_documents)`，当前只接受显式支持且哈希匹配的 v2.1。
- 支持“仅补政策、原始 JSON 不变”的补材料重跑；仍执行全部双方陈述与回应，不复制旧裁决。
- root CLI 从 catalog 枚举案例。新数据金额读取、fare 条件名、政策引用展示、置信度门槛做了兼容修复。原 Judge 的路线论证验证仍为既有合成结构；本案由官方 >2 km 门槛转人工，没有伪造验证事件来绕过它。

## 验证与复现

```powershell
$env:PYTHONUTF8 = '1'
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m unittest discover -s vendor/ryderesolve-evidence-tools/tests -v
.venv/Scripts/python.exe -m unittest discover -s vendor/ryderesolve-advocate-system/tests -v
.venv/Scripts/python.exe -m ryde_resolve.run_demo --output-dir outputs/official-offline-2026-10-15
node tests/test_ui_script.cjs outputs/official-offline-2026-10-15/ryde-evaluation.html
.venv/Scripts/python.exe vendor/ryderesolve-evidence-tools/tests/wheel_smoke.py
```

离线演示中的 escalate 是 OfflineJudge 占位输出，不能当成三案真实裁决结果。新增集成测试使用捕获输入的测试 provider 验证真正的 AdvocateSystem 接口和四次调用路径，不调用 Gemini/ADP。原 10 月 13 日模型结果与历史评估产物保留，不宣称在新规则下仍成立。

还修复了团队基线遗漏的 Evidence `ui.html/ui.js` 文件，以及 Windows 下评估导出换行导致文件哈希不匹配的问题。凭证相关 POSIX 权限测试在 Windows 明确跳过、在 Linux CI 执行；没有修改或放宽实际凭证检查。

本地结果、浏览器检查与 PR CI 状态应分别核对。GitHub Actions 增加 Windows/Linux × Python 3.12/3.14 离线矩阵，包含所有测试、四案演示和隔离 wheel 安装；没有在 CI 中配置模型凭证或真实调用。

2026-10-15 本地验证：Windows / Python 3.12，团队测试 131 项（127 通过、4 项因 POSIX 权限或符号链接权限跳过），Evidence 121/121，Advocate 15/15；共收集 267 项、263 通过、4 跳过。四案离线完整流程无 validation_errors；JS 案例切换/引用展开检查通过；隔离 wheel 安装后四案、政策文档与网页资源均可用。

实际浏览器核对了 Evidence 案例切换、DISP-002 §2.1 / DISP-003 §3.3 原文查询、团队页面免费等待和道路距离/金额显示、引用展开；下载的 DISP-002 完整快照通过团队 verify_snapshot，保留原 JSON 5.0 数字类型。未执行模型调用、退款或发布服务。CI 的具体结果以 PR 当前提交检查为准，不把本地结果代替远端结果。

## 交接给队友

1. Advocate：评审新增提示词与三类事实映射，真实重跑后核对论点引用；请勿混用旧 generated 快照/旧模型输出。
2. Judge：确认八分钟门槛、文档优先级的人工澄清路径；评审官方路线门槛、fare 条件、SGD 金额与置信度检查。
3. 团队：使用自己的授权完成最新版模型联调和展示。群内提交通知写明截止为 2026-10-16 23:59 GMT+8；PR 合并/比赛提交需要团队另行执行，本轮未代合并或提交。
