# 队友交接摘要

Advocate 包已完成代码与离线验证，可接你现有的编排。

- 使用与你 Evidence 模块相同的 Evidence Pack / Advocate Schema。
- 接口：AdvocateSystem(provider).run_advocate(pack, audit, side)。
- 输出：双方各一份 dict；默认互不看对方输出。
- 可选 run_pair(..., rebuttal=True)，保存双方初始和回应结果供展示。
- 可直接 Gemini REST，也可以 CallableProvider 复用你的 Gemini 函数。
- 15 项离线测试通过；两个案例均与真实 Evidence 模块完成离线契约联调。
- 还需你们配置真实 Gemini，保存双方实测输出，再接 Judge/UI。
- DISP-002 的计时缺口如实保留，不硬编码预期裁决。

建议先用共同的 snapshot 联调 DISP-002，再用已标记 synthetic 的 SYN-ROUTE-001。
不要把离线测试替身称为真实模型输出或把结构通过称为论证正确。
