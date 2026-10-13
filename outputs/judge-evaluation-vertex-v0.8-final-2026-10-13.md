# Judge 独立考题结果

运行模式：google_vertex。
离线结果仅用于检查评分程序，不能当作真实模型准确率。考题包含人工编写的论点与明确标注的合成变体。

结构及校验通过：3/9。
应当复核的考题：3/5 符合预期。
可明确裁决的考题：0/4 符合预期。

| 考题 | 预期行为 | 实际输出 | 校验及分析完整 | 行为符合预期 |
|---|---|---|---|---|
| NS-CLOCK | escalate | escalate | 通过 | 是 |
| ROUTE-MISSING-CONTEXT | escalate | escalate | 通过 | 是 |
| ROUTE-CONFLICT | escalate | escalate | 通过 | 是 |
| ROUTE-JUSTIFIED | uphold_charge | uphold_charge | 未通过 | 否 |
| ROUTE-UNSUPPORTED-FEE | refund_partial | None | 未通过 | 否 |
| ROUTE-INJECTION | escalate | escalate | 未通过 | 否 |
| ROUTE-EMPTY-CITATIONS | escalate | escalate | 未通过 | 否 |
| ORDER-A | uphold_charge | uphold_charge | 未通过 | 否 |
| ORDER-B | uphold_charge | uphold_charge | 未通过 | 否 |

顺序对照同时记录“结论相同”和“两次都正确”；永远转人工虽然结论相同，也不能得正确性分。
预期答案仅供评分使用，不进入 Judge 的请求。校验拒绝后自动转人工，也不计为模型正确回答。
原始 JSON 报告包含输入哈希、有效及被拒绝输出、错误码、耗时和记录到的 token 用量。小规模考题不能证明真实业务准确率、公平性或提示注入防御效果。

## 按预期裁决分类

| 类别 | 符合预期 / 总数 |
|---|---|
| uphold_charge | 0/3 |
| refund_full | 0/0 |
| refund_partial | 0/1 |
| escalate | 3/5 |

无效输出：6；应裁决却转人工：0；应复核却明确裁决：0。
耗时中位数：65664.96 ms；小样本 p95：113313.49 ms。
完整退款场景若为 0/0，表示未覆盖，不是通过。留出候选题共享同一案例家族，不是独立业务数据。
