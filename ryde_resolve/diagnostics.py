"""Plain-language explanations only; no ruling changes or inferred evidence truth."""
import re

MESSAGES={
    'CANNOT_SELF_RESOLVE_POLICY_OR_DATA':('模型的已解决标签与程序锁定的待澄清／待人工处理状态冲突；即使正文正确建议转人工，也不能把问题标成已解决。','继续保留人工或政策澄清出口，不能凭模型表态消除权限门槛。'),
    'SIDE_LEDGER_CONFLICT':('一方的整体评价与其逐条论点评价不一致。','对照每条论点和来源核对汇总；这不是新增证据。'),
    'ARGUMENT_ASSESSMENT_WITHOUT_RECORD_SUPPORT':('论点的引用类型不满足所选判断范围。记录了某人的说法，不等于证实了所述事件。','核对原论点的每个事实部分及原始记录，补齐相关依据或保留证据不足。'),
    'ARGUMENT_UNKNOWN_EVIDENCE':('论点引用了当前快照中不存在的证据编号。','使用当前快照的证据编号重新检查输出。'),
    'ARGUMENT_CONFLICTING_REFERENCE_ROLE':('同一证据被同时列为同一论点的支持和反证。','核对原始记录，分别说明支持与反驳的部分。'),
    'UNRESOLVED_DATA_OR_POLICY_REVIEW':('仍有影响裁决的证据、政策或输出检查问题，当前建议不能发布。','查看其他具体检查原因及待澄清事项。'),
    'RUN_CALL_BUDGET_EXHAUSTED':('本次允许的模型调用次数已用完。','保留现有输出，核对预算和恢复条件后再决定是否继续。'),
    'CHECKPOINT_INPUT_OR_VERSION_MISMATCH':('材料、提示词、接口或模型版本已变化，旧结果不能直接续用。','使用当前版本重新运行，保留旧记录。'),
}


def explain_checks(result):
    errors=result.get('validation_errors',[])
    phase='final' if errors else 'initial'
    errors=errors or result.get('judge_raw_validation_errors',[])
    output=[];seen=set()
    for error in errors:
        code=str(error).split(':',1)[0]
        match=re.search(r'/(opening|response)/(rider|driver)/(claims|counterpoints)/(\d+)(?:$|\s)',str(error))
        ref=match.group(0).strip() if match else None
        if (code,ref) in seen:continue
        seen.add((code,ref));claim=None
        if match:
            rnd,side,field,index=match.groups()
            rows=result.get('arguments',{}).get(rnd,{}).get(side,{}).get(field,[])
            if int(index)<len(rows):claim=rows[int(index)].get('claim')
        message,action=MESSAGES.get(code,('输出检查未通过，需要查看保留的原始错误。','按具体错误检查材料、输出或运行配置。'))
        if any(marker in code for marker in ('HTTP_','TIMEOUT','CONNECTION','ADC_')):
            message='模型调用、授权或连接失败，本次未形成可采纳结果。'
            action='检查具体错误和授权状态，确认恢复条件及预算。'
        output.append({'code':code,'phase':phase,'message':message,'next_action':action,
                       'argument_ref':ref,'claim':claim})
    if not result.get('validation_errors'):
        reason_messages={
            'policy_gate':('政策规定此案需要人工处理。','按人工交接单复核；这是正常政策出口。'),
            'policy_clarification':('政策与样例规则的关系尚未明确。','先确认适用规则，再决定是否能够自动处理。'),
            'missing_evidence':('影响裁决的材料仍有缺口。','按交接单补材料或由人工复核。')}
        for reason in result.get('review_reason_types',[]):
            if reason in reason_messages:
                message,action=reason_messages[reason]
                output.append({'code':reason,'phase':'policy','message':message,'next_action':action,
                               'argument_ref':None,'claim':None})
    return output
