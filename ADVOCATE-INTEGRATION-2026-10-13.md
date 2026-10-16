# 队友 Advocate 接入 · 2026-10-13

原包 `ryderesolve-advocate-system.zip` 共 27 个原始文件已保留在 `vendor/ryderesolve-advocate-system`。
两个核心 schema 与现有 Evidence 模块逐字节相同；安装后原文件哈希未改变。
队友原包自测 15 项通过；本地接口回归测试累计 124 项通过。

## 怎么接入

使用队友的 AdvocateSystem / CallableProvider，复用本地 Google Cloud Vertex ADC 传输。
未使用 Gemini API Key，不需重新申请钥匙，也没有把 ADC token 作为 API Key。
接入适配在 `ryde_resolve/teammate_advocate.py`，不改队友原始角色提示词或校验器。

```bash
.venv/bin/python -m ryde_resolve.run_demo --case DISP-002 --judge vertex --advocate teammate-vertex --thinking-level LOW --output-dir outputs/team-live-2026-10-13
```

该命令会发送案卷及双方论点到配置的 Google Cloud 项目：双方开场2次、对等回应2次、Judge1次，共5次模型请求。
运行时使用当前 Evidence 快照，而非队友包内复制的 JSON。
所有 Advocate 输出由队友模块和现有编排各校验一次，并绑定 snapshot_id / round。
开场不得看到对方输出；回应必须看到同快照下对方的开场，过期快照会被拒绝。
每次实际模型调用的安全用量元数据保存在通信日志 transport 中；不会保存授权 token。
默认仍为离线模式，模型失败不偷偷降级成占位内容或自动重试。

## 当前边界

JSON schema 与编号校验不能证明论点在语义上正确；Judge 检查也不是事实真实性认证。
一例跑通不代表所有纠纷都能正确裁决。明确收费／退款仍需适用政策和证据。
主办方 DISP-002 与队友合成 SYN-ROUTE-001 必须区分；没有新增官方 Route 数据。
实际联调结果见同日验证记录，尚未完成的地方不应描述为已验证。

## 实际联调结果

官方DISP-002已完成5次真实请求，20条论点进入Judge分析，validation_errors为空。
结果为escalate，退款金额未裁定；缺口仍是权威等待起算政策。
实测总耗时约80.7秒，记录43816 tokens；这不是费用账单。
真实结果页与JSON均保存于 `outputs/team-live-2026-10-13/`。
