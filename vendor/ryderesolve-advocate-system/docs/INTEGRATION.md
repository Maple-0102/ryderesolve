# 接入协议与验收

## 1. 输入与输出

`run_advocate(evidence_pack, audit=None, side='rider') -> dict`。
使用队友原版 Schema，不改变 frozen 字段；额外输出 policy_refs 已被原版支持。
所有顶层字段建议输出：case_id / side / position / claims / counterpoints / missing_information。
claims 和 counterpoints 每项用 claim / evidence_refs / policy_refs；missing_information 为字符串数组。
position 是一方诉求，不是 Judge decision；现有 Schema 未冻结 position 枚举，不要在编排层硬编码只接受 refund。

模型结果先校验：case、side、结构、有限 JSON 值和引用范围。失败抛 ContractError，不提交 Judge，不把失败当作人工裁决。空 evidence_refs 产生 warning，需要审查。语义支持与政策适用性仍由人工质量评估和 Judge 检查。

## 2. 优先复用 Evidence 快照

安装队友 Evidence 项目后：

```python
from ryderesolve_evidence import EvidenceTools
from ryderesolve_advocate import AdvocateSystem, CallableProvider

tools = EvidenceTools()
snapshot = tools.prepare_case('DISP-002')

# 改成你已有的 Gemini 函数：必须返回文本或 dict，不能返回整个 SDK response。
def model_call(system_text, user_text):
    return existing_gemini_call(system_text, user_text)

agents = AdvocateSystem(CallableProvider(model_call))
pair = agents.run_pair(snapshot['evidence_pack'], snapshot['audit'])
for side, output in pair['final'].items():
    check = tools.validate_outputs('DISP-002', advocate=output,
                                  expected_snapshot_id=snapshot['snapshot_id'])
    if not check['structurally_valid']:
        raise ValueError(check['errors'])
# 将 pair['final']['rider'] 和 pair['final']['driver'] 送入现有 Judge。
# 保存 snapshot_id / pair / 校验报告 / Judge 输出到同一条运行记录。
```

`existing_gemini_call` 是你们的函数占位名，不是本包提供的实现。
Vertex AI、自定义代理地址、异步 SDK 应通过你们自己的封装适配；本包原生 provider 只支持 Google AI Studio Gemini REST API，不支持 Vertex OAuth。

HTTP 编排也可先 GET `/cases/DISP-002/snapshot`，把下载的完整 JSON 作为 CLI --input。
不要用预生成 fixtures 的编号混配新快照。输入改变后重新运行双方 Agent。

## 3. 回应轮次

默认两次调用，双方彼此不可见。`run_pair(..., rebuttal=True)` 四次调用，双方第二轮都看到对方第一轮，不泄漏单方第二轮；initial/final 保留用于 UI 展示。
parallel=True 可同时调用双方，但要求自定义 provider 线程安全；默认关闭。
run_pair 的 envelope 不是 Advocate Schema。交给 Judge 的是里面的两个 final dict。

## 4. DISP-002 验收重点

- 乘客陈述可引用 E-002，但必须标明未独立验证。
- E-035 / E-036 / E-037 分别是 480 / 470 / 360 秒，不自行选择政策时钟。
- P-003 是免费等待，P-004 是 no-show 阈值，不能写死示例旧编号。
- 司机接触记录支持尝试联系，不证明乘客故意躲避。
- 系统记录收费不能循环证明政策正确；历史档案不能证明本案责任。
- 政策起算缺口留给 Judge，不要求它硬判退款或保留收费。

## 5. Route 验收

输入和 audit 必须保留 synthetic / team-authored 来源。路线长不等于司机责任。
核对参考路线覆盖范围、乘客同意、绕行原因、费用组成和明示政策；不足就说明缺口。

## 6. 交付验收清单

1. 本包离线测试通过；安装在你们环境中成功。
2. 两个案例各完成真实模型调用，保存模型、快照、输出和校验。
3. 人工检查每条引用确实支持论点，双方承认主要不利证据。
4. Judge 使用同一快照联调，UI 可展示 initial/final 与引用。
5. 单独用明确政策测试退款/保留收费/人工复核，不用改官方样例来迎合答案。

不得因技术测试通过宣称已完成公平性、安全性、比赛合规性验证。
