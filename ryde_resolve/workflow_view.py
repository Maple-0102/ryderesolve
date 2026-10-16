"""Derive readable progress from actual events, never a simulated animation."""
from .ui import esc


def timeline(result):
    events=result.get('communication_log',[])
    specs=[('prepare_case','准备证据'),('calculate_rules','检查政策'),('opening:rider','乘客开场'),('opening:driver','司机开场'),
           ('response:rider','乘客回应'),('response:driver','司机回应'),('judge','Judge 判断')]
    if any(e['step']=='judge_repair' for e in events):specs.append(('judge_repair','限次结构修复'))
    if result.get('workflow_options',{}).get('reviewer') or any(e['step']=='inference_review' for e in events):specs.append(('inference_review','推导复核'))
    specs.append(('validate_and_gate','结果检查'))
    rows=[]
    for key,label in specs:
        step,_,side=key.partition(':')
        matches=[e for e in events if e['step']==step and (not side or e['agent'].startswith(side+' '))]
        if matches:
            e=matches[-1];status=e['status'];error=e.get('error');duration=e.get('duration_ms')
        else:
            status='pending';error=None;duration=None
            if result.get('execution_status')=='completed' or result.get('providers_skipped'):status='skipped'
        rows.append({'key':key,'label':label,'status':status,'error':error,'duration_ms':duration})
    return rows


def render_timeline(result):
    labels={'success':'完成','reused':'复用已有结果','failed':'失败','interrupted':'中断','running':'进行中','pending':'尚未执行','skipped':'未执行／不适用'}
    rows=''.join('<li><b>'+esc(r['label'])+'</b>：'+esc(labels.get(r['status'],r['status']))+
        (' · '+esc(r['error']) if r['error'] else '')+'</li>' for r in timeline(result))
    reasons=result.get('review_reason_types',[])
    next_action=('检查失败记录和预算，确认相同版本后续跑。' if result.get('execution_status') in ('failed','interrupted') else
        '政策要求人工处理；补充材料不能解除该权限门槛。' if 'policy_gate' in reasons else
        '等待有来源的新材料或政策澄清；不能靠重复讨论消除缺口。' if result.get('business_decision_status')=='awaiting_human' else
        '检查建议及其依据；本系统不执行收费或退款。')
    return '<section><h3>流程进度</h3><p class="muted">根据实际执行事件生成；静态报告是事后记录。</p><ol class="flow-progress">'+rows+'</ol><p>下一步：'+esc(next_action)+'</p></section>'
