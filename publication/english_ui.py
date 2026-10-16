"""Translate only the published report presentation; retain raw JSON and scripts exactly."""
from pathlib import Path
import hashlib, html, json, re
from html.parser import HTMLParser

ROOT=Path('outputs/pages-publication-2026-10-16')
SITE=ROOT/'site'
SOURCE=Path('outputs/latest-flow-2026-10-16/recording')
TRANSLATIONS={
'案件证据与政策可逐条核对来源。运行模式见每个案件；离线结果不代表真实模型裁决。本页是一次运行的快照，切换案件不会发起模型请求。':'Follow each evidence and policy reference to its source. Provider mode is shown per case; offline outputs are not live-model rulings. This is a saved run snapshot. Changing cases does not call a model.',
'程序保留原输出，对不满足来源要求的论点降低支持评级，或按逐条评价修正汇总标签，然后重新检查全部规则。Fare 仅在政策条件及主依据独立成立时允许此修正；裁决与金额不变，未执行任何收费或退款。':'The program preserves the original output, downgrades argument ratings that lack the required source support or reconciles summary labels with individual assessments, then rechecks all rules. For Fare, these adjustments are allowed only when the material policy conditions and main supporting evidence independently hold. The recommendation and amount remain unchanged; no charge or refund is executed.',
'已保留的原始候选问题：仍有影响裁决的证据、政策或输出检查问题，当前建议不能发布。':'Preserved original candidate issue: evidence, policy or output-check problems still affect the recommendation, so that candidate cannot be released.',
'已保留的原始候选问题：论点的引用类型不满足所选判断范围。记录了某人的说法，不等于证实了所述事件。':'Preserved original candidate issue: the cited source types do not support the selected assessment scope. A record of a statement does not establish that the described event occurred.',
'当前阻止发布的问题：模型把必须澄清或由人工处理的问题标成了已解决，但现有材料不能解除这个限制。':'Current blocking issue: the model marked an issue requiring clarification or human authority as resolved, but the available materials cannot remove that restriction.',
'当前阻止发布的问题：论点的引用类型不满足所选判断范围。记录了某人的说法，不等于证实了所述事件。':'Current blocking issue: the cited source types do not support the selected assessment scope. A record of a statement does not establish that the described event occurred.',
'请主办方明确案内 8 分钟 no-show 阈值起算点，以及与 v2.1 §2.1 五分钟规则的关系和来源优先级。':'Ask the organizer to clarify the start event for the embedded 8-minute no-show threshold, its relationship to the 5-minute rule in v2.1 Section 2.1, and source precedence.',
'保留两份来源及缺失标记；收到可追溯的正式澄清后显式更新政策版本并重跑。':'Retain both sources and the missing-information flags. After receiving traceable official clarification, explicitly update the policy version and rerun.',
'修复失败步骤并运行回归测试，然后对同一案卷重新执行完整流程。':'Fix the failed step and run regression checks, then rerun the complete workflow on the same case file.',
'先确认适用规则，再决定是否能够自动处理。':'Confirm the applicable rule before deciding whether automatic handling is permitted.',
'将当前证据、政策原文和双方陈述交人工审核；AI 仅整理材料，不据此自动裁决。':'Refer the current evidence, original policy text and both sides of the argument to a human reviewer. AI organizes the materials without automatically adjudicating this case.',
'提供权威政策或更正后的源数据；保留变更来源，重建快照后重跑，不能只修改 resolved 标签。':'Supply authoritative policy or corrected source data, retain the change provenance, rebuild the snapshot and rerun. Merely changing the resolved label is insufficient.',
'查看其他具体检查原因及待澄清事项。':'Inspect the other specific check failures and outstanding clarification requests.',
'核对原论点的每个事实部分及原始记录，补齐相关依据或保留证据不足。':'Check each factual part of the original argument against the underlying records. Add relevant support or retain an insufficient-evidence assessment.',
'核对该论点所需记录，取得新材料后重建快照；如无法取得则保留缺失状态。':'Identify the records needed for this argument. Rebuild the snapshot after obtaining new material; otherwise retain the missing-information status.',
'检查失败记录和预算，确认相同版本后续跑。':'Inspect the failure record and budget, verify version compatibility, then resume.',
'检查建议及其依据；本系统不执行收费或退款。':'Inspect the recommendation and its supporting records. This system does not execute charges or refunds.',
'由 Evidence 方补充可追溯记录、重建案卷快照，再重新运行分析。':'The Evidence owner should add traceable records, rebuild the case snapshot and rerun the analysis.',
'确认材料来源并补充案卷，再重新分析。':'Verify the material provenance, supplement the case file and rerun the analysis.',
'等待有来源的新材料或政策澄清；不能靠重复讨论消除缺口。':'Wait for new sourced material or policy clarification. Repeating the debate cannot fill the gap.',
'继续保留人工或政策澄清出口，不能凭模型表态消除权限门槛。':'Retain the human-review or policy-clarification path. A model assertion cannot remove an authority threshold.',
'定位本次输出检查中的错误码并修复对应模块输出。':'Identify the error codes in this output check and fix the corresponding module output.',
'提供有来源的改道背景与额外收费依据核实记录；司机陈述本身不够。':'Provide sourced records verifying the reason for the detour and the basis for the additional charge. The driver statement alone is insufficient.',
'免费等待起点已明确，但不足以决定争议收费条件。':'The free-wait start is defined, but this alone does not establish the conditions for the disputed charge.',
'决定改道是否有依据、额外收费是否成立。':'Affects whether the detour is justified and whether the additional charge is supported.',
'官方政策规定本案必须由人工裁决；补齐材料不能免除该门槛。':'The official policy requires human adjudication for this case. Supplementing the evidence cannot remove this threshold.',
'当前未产生可采纳的裁决输出。':'No acceptable ruling output is currently available.',
'影响关键政策或数据条件是否成立。':'Affects whether a material policy or data condition is established.',
'缺少裁决所需的关键材料。':'Material records required for a ruling are missing.',
'该论点暂不能按已确认事实采用；不等于对方自动成立。':'This argument cannot currently be accepted as an established incident fact. This does not automatically establish the opposing argument.',
'以下为通过结构和引用检查的分析；这些检查不能证明自然语言推理正确。':'The analysis below passed structural and reference checks. Those checks do not establish that the natural-language reasoning is correct.',
'根据实际执行事件生成；静态报告是事后记录。':'Generated from actual execution events. This static report is a record of a completed run.',
'格式和编号有效，不等于模型理解正确。':'Valid structure and identifiers do not establish correct model understanding.',
'正常人工处理原因：政策与样例规则的关系尚未明确。':'Human-review reason: the relationship between the policy and the embedded sample rules remains unclear.',
'每条政策保留案卷中的来源标签；团队程序检查不代表平台收费政策。':'Each policy retains its source label from the case file. Team-defined program checks are not platform charging policy.',
'点击编号或展开条目查看本次快照的原始记录。':'Click an identifier or expand an item to inspect the original records in this snapshot.',
'由编排层生成的待办建议；未发送通知，也未自动执行操作。':'Suggested tasks generated by the orchestration layer. No notifications have been sent and no actions have been executed automatically.',
'真实模型调用的保存记录：展示这次运行结果；打开本页不会再次调用模型。':'Saved real-model report: this page displays the recorded run. Opening it does not call the model again.',
'算术结果与已明确的规则分开列出；未明示的收费条件仍需澄清。距离／差额不等于责任／退款。':'Calculations are shown separately from explicit rules. Unspecified charging conditions still require clarification. Distance or fare differences alone do not establish liability or a refund.',
'这是事后记录，页面不执行退款。请同时展示原始检查与程序修正。':'This is a saved report; the page does not execute refunds. Inspect both the original checks and the program adjustments. Original JSON payloads are retained in their source language.',
'offline_placeholder 只摘录已有陈述，不代表已完成真实 Agent 辩论。':'offline_placeholder only extracts existing statements; it does not represent a completed live-agent debate.',
'本次没有通过检查的结构化分析，请查看复核原因和输出检查。':'No structured analysis passed validation in this run. Inspect the review reasons and output checks.',
'本次分析未列出额外缺失信息。':'No additional missing information was listed in this analysis.',
'暂无可采纳的裁决依据。':'No acceptable ruling findings are available.',
'主办方样例 · 非真实运营数据证明':'Organizer-supplied example · not verified production data',
'官方 Fare：未通知加价':'Official Fare sample: unannounced fare increase',
'官方 Route：超出 AI 权限':'Official Route sample: beyond AI authority',
'官方 No-show：政策待澄清':'Official No-show sample: policy clarification required',
'争议证据与裁决工作台':'Dispute Evidence and Decision Workbench',
'Judge 如何看双方观点':'How the Judge Assesses Both Sides',
'执行状态与恢复':'Execution Status and Recovery',
'流程失败：尚无可采纳裁决':'Execution failed: no acceptable ruling available',
'流程失败／待恢复':'Execution failed / recovery required',
'流程已完成':'Execution completed',
'流程进度':'Workflow Progress',
'检查原因与下一步':'Check Findings and Next Steps',
'本次结果':'Run Result',
'已记录的依据':'Recorded Findings',
'查看最终 JSON':'View Final JSON',
'计算结果与待澄清问题':'Calculations and Open Questions',
'人工交接单':'Human Review Handoff',
'核心问题':'Core Question',
'仍需补充的信息':'Missing Information',
'争议点分析':'Disputed Issues',
'逐条论点评估':'Per-Argument Assessments',
'复核问题逐项处理':'Review Issues and Dispositions',
'裁决关键条件':'Material Decision Conditions',
'先例对照':'Precedent Comparison',
'来源、信心因素与分项动作':'Sources, Confidence Factors and Component Actions',
'逐项政策条件':'Policy Conditions',
'程序保守修正':'Conservative Program Adjustments',
'原始 Judge 建议':'Original Judge Recommendation',
'原始模型检查错误':'Original Model Validation Errors',
'逐条修正记录':'Adjustment Audit',
'双方陈述与回应':'Arguments and Responses from Both Sides',
'第一轮陈述':'Opening Argument',
'回应对方':'Response to the Other Side',
'乘客 Advocate':'Rider Advocate',
'司机 Advocate':'Driver Advocate',
'证据与原文':'Evidence and Source Records',
'政策与原文':'Policies and Source Records',
'通信日志':'Communication Logs',
'输出检查':'Output Checks',
'本次绑定的政策与程序检查':'Bound Policy and Program Checks',
'查看团队检查约定':'View Team Validation Contract',
'调用、复用与预算':'Calls, Reuse and Budgets',
'第二轮争议点与引用进展':'Round-Two Issues and Citation Progress',
'返回演示目录':'Back to Demo Home',
'准备证据':'Prepare Evidence',
'检查政策':'Check Policy',
'乘客开场':'Rider Opening',
'司机开场':'Driver Opening',
'乘客回应':'Rider Response',
'司机回应':'Driver Response',
'Judge 判断':'Judge Review',
'结果检查':'Validate Result',
'政策要求人工裁决':'Policy Requires Human Adjudication',
'等待政策澄清':'Awaiting Policy Clarification',
'模型输出未通过检查':'Model Output Failed Validation',
'人工审核门槛':'Human-Review Threshold',
'缺少支持证据':'Supporting Evidence Missing',
'规则来源':'Rule Source',
'需 Judge 分析':'Judge Analysis Required',
'必须补充政策或数据':'Policy or Data Supplement Required',
'仅供提示':'Advisory Only',
'乘客观点':'Rider Position',
'司机观点':'Driver Position',
'部分有依据支持':'Partly Supported',
'有依据支持':'Supported',
'有支持':'Supported',
'仍待澄清':'Clarification Still Required',
'待人工复核':'Awaiting Human Review',
'建议部分退款':'Partial Refund Recommended',
'建议负责人：':'Suggested Owner: ',
'主办方／平台政策负责人':'Organizer / Platform Policy Owner',
'人工复核负责人':'Human Review Owner',
'客服／证据负责人':'Customer Support / Evidence Owner',
'平台政策／数据负责人':'Platform Policy / Data Owner',
'平台运营／证据负责人':'Platform Operations / Evidence Owner',
'集成／Judge 开发负责人':'Integration / Judge Developer',
'差额（未裁定退款）':'difference (not a refund determination)',
'（未裁定退款）':' (not a refund determination)',
'从预约时间起 5 分钟；结束：':'5 minutes from the scheduled pickup time; ends at: ',
'政策免费等待':'Policy Free-Wait Window',
'报告道路距离':'Reported road distance',
'采样路线':'Sampled route',
'原记录金额':'Amount in the source record',
'原文路径：':'Source path: ',
'来源：':'Source: ',
'类型：':'Type: ',
'依据：':'Evidence: ',
'政策：未引用':'Policy: no references',
'政策：':'Policy: ',
'支持记录：无':'Supporting records: none',
'支持记录：':'Supporting records: ',
'反驳记录：无':'Opposing records: none',
'反驳记录：':'Opposing records: ',
'涉及论点：':'Arguments: ',
'相似点：':'Similarities: ',
'差异：':'Differences: ',
'待补充：未列出':'Missing information: none listed',
'待补充：':'Missing information: ',
'需要补充：':'Information needed: ',
'影响：':'Impact: ',
'下一步：':'Next step: ',
'原论点：':'Original argument: ',
'业务状态：':'Business status: ',
'；首次输出通过：':'; Raw first pass valid: ',
'退款金额：':'Refund amount: ',
'页面只展示建议，不执行收费或退款。':'This page displays recommendations only; it does not execute charges or refunds.',
'未裁定':'Not determined',
'不满足':'Not met',
'满足':'Met',
'未知':'Unknown',
'生效 ':'Effective ',
'快照 ':'Snapshot ',
'运行 ':'Run ',
'参考 ':'Reference ',
'差额 ':'Difference ',
' 秒':' seconds',
' 分钟':' minutes',
'：完成':': Completed',
'选择案件':'Choose a Case',
}
PROTECTED=re.compile(r'(<(?:pre|script|style)\b[^>]*>.*?</(?:pre|script|style)>)',re.S|re.I)
CJK=re.compile(r'[\u3400-\u9fff]')
ordered=sorted(TRANSLATIONS.items(),key=lambda x:len(x[0]),reverse=True)
class Structure(HTMLParser):
 def __init__(self):super().__init__();self.tags=[];self.refs=[]
 def handle_starttag(self,t,attrs):
  a=dict(attrs);self.tags.append(t)
  self.refs.extend((t,k,v) for k,v in attrs if k in ('id','href','src','data-case','aria-controls'))
checks=[]
for source in sorted(SOURCE.glob('r21-*.html')):
 original=source.read_text()
 pieces=PROTECTED.split(original)
 unresolved=[]
 for i in range(0,len(pieces),2):
  text=pieces[i]
  for cn,en in ordered:text=text.replace(cn,en)
  text=text.replace('lang="zh-CN"','lang="en"')
  pieces[i]=text
  unresolved += re.findall(r'[^<>\n]*[\u3400-\u9fff][^<>\n]*',text)
 if unresolved:
  print(source.name,'UNTRANSLATED:',*sorted(set(unresolved)),sep='\n')
  raise SystemExit(1)
 translated=''.join(pieces)
 translated=translated.replace('<h1>Dispute Evidence and Decision Workbench</h1>', '<h1>Dispute Evidence and Decision Workbench</h1><p class="eyebrow">Built by Team AgentForge</p>', 1)
 assert PROTECTED.findall(original)==PROTECTED.findall(translated),'Raw JSON, CSS or scripts changed'
 a=Structure();a.feed(original);b=Structure();b.feed(translated.replace('<p class="eyebrow">Built by Team AgentForge</p>','',1))
 assert a.tags==b.tags and a.refs==b.refs,'Document structure or reference targets changed'
 (SITE/source.name).write_text(translated)
 checks.append({'file':source.name,'original_sha256':hashlib.sha256(original.encode()).hexdigest(),'english_sha256':hashlib.sha256(translated.encode()).hexdigest(),'raw_payloads_and_scripts_preserved':True,'structure_and_references_preserved_except_team_credit':True,'team_credit':'Built by Team AgentForge','untranslated_ui_texts':0})
landing=SITE/'index.html'
text=landing.read_text().replace('Report interface: Chinese; model arguments and source data: English.','Report interface: English. Original JSON payloads retain their source language.').replace('Use “返回演示目录” at the top to return here.','Use “Back to Demo Home” at the top to return here.')
assert not CJK.search(text)
landing.write_text(text)
(ROOT/'english-ui-checks.json').write_text(json.dumps(checks,indent=2))
print('English report presentation verified; original raw payloads, scripts, structure and reference targets preserved.')
