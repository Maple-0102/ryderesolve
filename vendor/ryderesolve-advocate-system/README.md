# RydeResolve Advocate System

给 Siqi 的独立交付包：Rider / Driver Advocate，兼容队友 Evidence Tools v0.2 接口。

## 当前状态（必须区分）

- 已实现：双方角色 prompt、Gemini REST 调用、自定义模型适配、JSON Schema 与引用校验、对等回应轮次、CLI、集成例子。
- 已做离线测试：见 `docs/TEST_REPORT.txt`；无密钥、不连接模型。
- 尚未完成：真实 Gemini 调用、队友 Judge/UI 联调、论证质量评估。此包不包含冒充真实模型输出的 JSON。
- 不实现 Evidence 规范化、Judge、UI、语音、自动退款或政策网站抓取。

## 安装 / 离线检查

Python 3.10+，在本包根目录：

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
python examples/check_fixture.py
```

## 跑真实模型（会产生模型调用费用）

从你们自己的账号设置后端环境变量；不要把密钥发到群里、截图或提交 Git。
模型名称使用 Judge 当前可用的名称，本包不假设某一型号一直可用。

```bash
export GEMINI_API_KEY='YOUR_LOCAL_KEY'
export GEMINI_MODEL='YOUR_ENABLED_MODEL'
python -m ryderesolve_advocate --input examples/input/DISP-002.evidence_pack.json --audit examples/input/DISP-002.audit.json --output runs/disp002-live-01
python -m ryderesolve_advocate --input examples/input/SYN-ROUTE-001.evidence_pack.json --audit examples/input/SYN-ROUTE-001.audit.json --output runs/route-live-01
```

PowerShell 使用 `$env:GEMINI_API_KEY='...'` 和 `$env:GEMINI_MODEL='...'`。`.env.example` 是模板，不会自动加载。模型配置缺失、输出非法或调用失败时明确报错，不偷偷退回模板输出。

输出目录含 `rider.json`、`driver.json`、`run.json`。增加 `--rebuttal` 会从两次模型调用变为四次：双方初始陈述，再分别看到对方初始陈述后回应。目录必须不存在，避免覆盖历史运行。

## 给编排队友

看 `docs/INTEGRATION.md` 和 `examples/integrate_evidence.py`。最小集成：

```python
from ryderesolve_advocate import AdvocateSystem, GeminiProvider

agents = AdvocateSystem(GeminiProvider.from_env())
rider = agents.run_advocate(pack, audit, side="rider")
driver = agents.run_advocate(pack, audit, side="driver")
# 将 rider 和 driver 两个 dict 交给你现有的 Judge。
```

顺序执行不意味着司机会看到乘客输出：默认双方独立读同一 Evidence Pack。自定义模型封装见集成文档。

## 数据来源及边界

两个输入 pack/audit 和两个 contracts 原样来自用户提供的 `ryderesolve-evidence-tools-main.zip`。
DISP-002 是赛事提供的样例来源，不视为经确认的真实乘客数据；SYN-ROUTE-001 是队友合成案例，包含团队自拟政策，不是官方 Route Deviation 数据。这里只复制运行输入，没有复制 evaluation 答案。

Schema 校验和编号存在性不能证明论点正确、安全性或裁决公平。prompt 的安全要求也不是安全认证。只用于私有 hackathon 原型；接入真实数据前需要隐私、安全和业务审核。Judge 保持最终裁决权。

官方 Gemini REST 参考（开发时核对）：
- https://ai.google.dev/api/generate-content
- https://ai.google.dev/api
