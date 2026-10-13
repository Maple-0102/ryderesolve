# 团队协作

`main` 保存共同确认的可运行版本。每个人新建分支修改，通过 Pull Request 合并。
建议分支名前缀：`evidence/`、`advocate/`、`judge/`。

- Evidence 维护 `vendor/ryderesolve-evidence-tools/`。
- Advocate 维护 `vendor/ryderesolve-advocate-system/`。
- Judge / Orchestration 维护 `ryde_resolve/`、`prompts/`、`schemas/` 及整体评估。
- 公共字段、编号、输入输出结构修改前在群里确认，并在 PR 写清影响。
- 合并前运行与改动相关的本地测试。真实模型评估需明确执行，会使用调用者项目额度。
- `.local/`、`.env`、ADC、密钥、虚拟环境和本机 SDK 不进仓库。
- 数据保留 official / synthetic 来源标识。缺少政策时保留不确定性，不虚构官方规则。

PR 描述写清：改了什么、为什么、怎么验证，以及是否修改接口。
当前没有配置强制分支保护，以上为团队协作约定。
