"""Local, actionable review checklist. Generated after gating, never a model action."""
from .review_policy import review_plan


def build_handoff(result):
    if result['ruling']['decision'] != 'escalate': return []
    items = []
    def add(code, needed, owner, impact, next_step):
        items.append({'issue_code': code, 'requested_information': needed, 'suggested_owner': owner,
                      'decision_impact': impact, 'next_action': next_step})
    s = result.get('snapshot')
    analysis = result['ruling'].get('case_analysis') or {}
    resolved = {r['issue_code'] for r in analysis.get('review_responses', []) if r['status'] == 'resolved'}
    if s:
        for issue in review_plan(s)['items']:
            if issue['category'] == 'informational' or (issue['category'] == 'judge_analysis' and issue['code'] in resolved): continue
            if issue['code'] in {'ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW', 'DISPUTE_VALUE_REQUIRES_HUMAN_REVIEW', 'SAFETY_INDICATOR_REQUIRES_HUMAN_REVIEW'}:
                add(issue['code'], issue['message'], '人工复核负责人',
                    '官方政策规定本案必须由人工裁决；补齐材料不能免除该门槛。',
                    '将当前证据、政策原文和双方陈述交人工审核；AI 仅整理材料，不据此自动裁决。')
            elif issue['code'] in {'NO_SHOW_THRESHOLD_CLOCK_UNSPECIFIED', 'POLICY_SOURCE_CONFLICT'}:
                add(issue['code'], '请主办方明确案内 8 分钟 no-show 阈值起算点，以及与 v2.1 §2.1 五分钟规则的关系和来源优先级。',
                    '主办方／平台政策负责人', '免费等待起点已明确，但不足以决定争议收费条件。',
                    '保留两份来源及缺失标记；收到可追溯的正式澄清后显式更新政策版本并重跑。')
            elif issue['category'] == 'judge_analysis':
                add(issue['code'], '提供有来源的改道背景与额外收费依据核实记录；司机陈述本身不够。',
                    '平台运营／证据负责人', '决定改道是否有依据、额外收费是否成立。',
                    '由 Evidence 方补充可追溯记录、重建案卷快照，再重新运行分析。')
            else:
                add(issue['code'], issue['message'], '平台政策／数据负责人',
                    '影响 no-show 计费条件或案卷数据是否足以支持裁决。' if s['evidence_pack']['dispute_type'] == 'no_show_charge' else '影响关键政策或数据条件是否成立。',
                    '提供权威政策或更正后的源数据；保留变更来源，重建快照后重跑，不能只修改 resolved 标签。')
    applied=result.get('calculations',{}).get('policy_application')
    if applied:
        for gate in applied['mandatory_human_review']:
            if any(item['issue_code']==gate['code'] for item in items):
                continue
            add(gate['code'],gate['reason'],'人工复核／政策负责人',
                '政策门槛尚未满足，AI不能通过自评高分或照抄样例建议放行。',
                '保留原始数据、政策版本和争议差额；由人工确认政策优先级或完成审核。')
    if result.get('reviewer_blocked'):
        add('INFERENCE_REVIEW', '；'.join(c['explanation'] for c in result['inference_review']['checks'] if c['status']!='clear'),
            '人工复核负责人','推导复核发现未排除的问题；原始 Judge 提案保留但不执行。',
            '核对复核员指向的结论、原文摘录和反证；由人工决定，不通过投票或高分覆盖。')
    if result['validation_errors']:
        add('PIPELINE_OUTPUT_REJECTED', '定位本次输出检查中的错误码并修复对应模块输出。', '集成／Judge 开发负责人',
            '当前未产生可采纳的裁决输出。', '修复失败步骤并运行回归测试，然后对同一案卷重新执行完整流程。')
    if result['modes']['judge'] == 'offline_review':
        add('OFFLINE_JUDGE', '完成模型配置并评估真实 Judge 输出。', 'Judge 开发负责人',
            '离线结果仅是分析骨架，尚未作出模型判断。', '用独立考题验证后显式开启 remote；记录模型版本与运行结果。')
    if result['modes']['advocate'] == 'offline_placeholder':
        add('OFFLINE_ADVOCATE', '提供当前快照的双方陈述与回应。', 'Advocate 开发负责人',
            '尚未运行真实双方辩论。', '按现有接口或快照绑定 JSON 接入四份输出，再联调。')
    for row in analysis.get('argument_assessments', []):
        if row['assessment'] in ('insufficient_evidence', 'unresolved') and row['missing_information'] and result['modes']['judge'] != 'offline_review':
            add('ARGUMENT_GAP:' + row['argument_ref'], '；'.join(row['missing_information']), '客服／证据负责人',
                '该论点暂不能按已确认事实采用；不等于对方自动成立。', '核对该论点所需记录，取得新材料后重建快照；如无法取得则保留缺失状态。')
    for i, gap in enumerate(analysis.get('missing_information', [])):
        if result['modes']['judge'] != 'offline_review':
            add(f'CASE_INFORMATION_GAP:{i}', gap, '客服／证据负责人', '缺少裁决所需的关键材料。', '确认材料来源并补充案卷，再重新分析。')
    if not items:
        add('MANUAL_REVIEW', '；'.join(result['ruling'].get('uncertainties', [])), '人工复核负责人',
            '目前没有可执行的确定性裁决。', '检查案卷、双方论点和复核原因；说明还需哪些材料后再重跑。')
    return items
