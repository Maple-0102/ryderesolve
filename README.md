# RydeResolve

Tencent Cloud 黑客松团队项目：Evidence + Advocate + Judge / Orchestration。
共同起点为 2026-10-13 v0.9；本分支在此基础上接入官方 DISP-001 / DISP-002 / DISP-003 和政策 v2.1，更新 Evidence 至 v0.3。SYN-ROUTE-001 继续保留为合成回归案例。

当前团队仓库是 **Maple-0102/ryderesolve**。本轮变更通过 PR 评审，后续协作以本库为准。
新增数据、政策冲突、兼容接口与验证说明见 [官方数据接入记录](docs/EVIDENCE-v0.3-OFFICIAL-2026-10-15.md)。新政策下尚未重跑真实模型；下方 Gemini 结果仅属于 10 月 13 日旧快照。

## 安装与离线运行

需要 Python 3.12+，在仓库根目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m ryde_resolve.run_demo
```

Windows 用 `.venv\Scripts\python.exe` 替代 `.venv/bin/python`。
默认使用真实 Evidence 模块、占位 Advocate 和离线 Judge，不产生模型调用费用。
生成的 `outputs/ryde-evaluation.html` 是静态记录，打开或切换页面不会调用模型。

## 团队分工与代码位置

| 部分 | 目录 |
| --- | --- |
| Evidence / Data / tools | `vendor/ryderesolve-evidence-tools/` |
| Advocate | `vendor/ryderesolve-advocate-system/` |
| Judge / 编排 / 整合 UI | `ryde_resolve/`、`prompts/`、`schemas/` |
| 测试和评估 | `tests/`、`evaluation/` |

队友提供的两个模块保留在 vendor 中。核心 Evidence / Advocate schema 未另造一套。
Judge 接入说明见 [Advocate 联调说明](docs/ADVOCATE-INTEGRATION-2026-10-13.md) 和 [v0.8 集成约定](docs/INTEGRATION-v0.8.md)。
协作流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 历史验证结果（2026-10-13 旧快照）

- 本地集成测试 124 项通过，Advocate 原包测试 15 项通过。
- 官方 DISP-002：4 次 Advocate + 1 次 Judge 真实调用，20 条论点，`validation_errors=[]`。
- 当时最终 `escalate`：当时尚未收到 v2.1，等待起算规则缺失。新版 §2.1 明确免费等待从预约时间起算，但案例内 8 分钟阈值的起点及两份来源的优先级仍待澄清。
- 最近一次完整 Judge 开发集严格通过 8/9；金额标签修正后专项复测 1/1。不能拼成最新版 9/9。
- 已导出 15 个合成/衍生测试输入：9 个开发题、6 个尚未实测的留出候选。仅来自两个种子家族，不是官方标准答案或现实准确率。

[完整验证记录](docs/VALIDATION-2026-10-13.md) · [已完成的真实运行页面](outputs/team-live-2026-10-13/ryde-evaluation.html)

## 运行真实 Gemini 流程

以下命令会调用 Google Cloud 并消耗对应项目额度。先配置自己的授权，禁止提交或转发其他成员的凭证。
当前适配器要求 SDK 位于 `.local/google-cloud-sdk/bin/gcloud`，ADC 位于 `.local/gcloud/application_default_credentials.json`。其他电脑需单独安装 SDK 到该路径（或在本机建立对应链接），并用自己的账号配置 ADC；ADC 的 quota project 必须与配置的 project 一致，凭证文件权限需为 600。Windows 当前建议用 WSL 运行真实云端流程。相关配置和凭证只保留在本机 `.local/`，不能直接复制其他成员的 `.local/`。

在 `.local/vertex-config.json` 配置自己的 Google Cloud 项目：

```json
{
  "project": "YOUR_PROJECT_ID",
  "model": "gemini-3.8-flash",
  "location": "global"
}
```

使用模型需要该账号/项目支持相应模型。仓库不包含登录凭证，也不会替成员创建付费资源。

```bash
.venv/bin/python -m ryde_resolve.run_demo --case DISP-002 --judge vertex --advocate teammate-vertex --thinking-level LOW --output-dir outputs/team-live-local
```

这是已实测的模型与调用配置；项目默认运行仍为离线模式。
ADP 适配器已保留，但未部署或验证云端应用，不能称为腾讯 ADP 实际运行结果。

## 本地测试

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s vendor/ryderesolve-advocate-system/tests -v
.venv/bin/python -m unittest discover -s vendor/ryderesolve-evidence-tools/tests -v
```

这些是本地测试，其中部分会启动本机 HTTP 模拟服务，不调用付费模型。
评估数据中的 `scorer-only-labels.json` 只用于评分，不能发送给模型。
Windows 请设置 `PYTHONUTF8=1` 或在 Python 命令后加 `-X utf8`。POSIX 凭证权限测试在 Windows 跳过，Linux CI 运行；真实云端适配器仍按原说明使用 Linux/WSL，本轮没有放宽凭证权限。

## 下一步

1. 评审官方数据接入 PR，确认政策来源冲突的处理；不复用旧 snapshot_id 的 Agent 输出。
2. Advocate/Judge 负责人用自己的授权重跑三份官方样例并检查引用、计时解释与金额语义。
3. DISP-001 超出距离 4.3 km，政策 §6.2 要求转人工；不要用样例中的推荐裁决绕过此门槛。
4. 原有评估集是旧规则下的合成测试；确认新规则后另行冻结新的真实模型评估，不混合版本汇总准确率。
5. 准备演示、提交材料和实际 CodeBuddy / WorkBuddy 使用证明。
