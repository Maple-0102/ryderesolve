"""Self-contained review UI; escaped source data, no credentials or external assets."""
import html
import json
from pathlib import Path
from ryderesolve_evidence.core import pointer
from .review_policy import review_plan


def esc(value):
    return html.escape(str(value), quote=True)


def pretty(value):
    return '<pre>' + esc(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)) + '</pre>'


def render_html(results, output_path='outputs/ryde-evaluation.html'):
    if isinstance(results, dict):
        results = [results]
    nav, panels = [], []
    for i, result in enumerate(results):
        prefix = f'case-{i}'
        s = result.get('snapshot')
        ruling = result['ruling']
        handoff_rows = ''.join(f'<li><b>{esc(x["issue_code"])}</b><p>需要补充：{esc(x["requested_information"])}</p><p>建议负责人：{esc(x["suggested_owner"])}</p><p>影响：{esc(x["decision_impact"])}</p><p>下一步：{esc(x["next_action"])}</p></li>' for x in result.get('human_handoff', []))
        handoff_html = f'<section><h3>人工交接单</h3><p class="muted">由编排层生成的待办建议；未发送通知，也未自动执行操作。</p><ul>{handoff_rows}</ul></section>' if handoff_rows else ''
        nav.append(f'<button role="tab" id="tab-{i}" aria-controls="{prefix}" aria-selected="{str(i == 0).lower()}" data-case="{prefix}">{esc(result["case_id"])}</button>')
        def links(refs, kind):
            return ' '.join(f'<a class="ref" href="#{prefix}-{kind}-{esc(ref)}">{esc(ref)}</a>' for ref in refs)
        if not s:
            panels.append(f'<article id="{prefix}" role="tabpanel" {"hidden" if i else ""}><h2>{esc(result["case_id"])}</h2><p>案例加载失败，已阻止裁决。</p>{pretty(ruling)}{handoff_html}</article>')
            continue
        origin = '主办方样例 · 非真实运营数据证明' if s['audit']['data_origin'] == 'organizer_sample' else '团队合成案例 · 政策也是合成规则'
        decision = {'escalate': '待人工复核', 'uphold_charge': '建议保留收费',
                    'refund_full': '建议全额退款', 'refund_partial': '建议部分退款'}.get(ruling['decision'], ruling['decision'])
        calculations = []
        for metric in result['calculations'].get('calculations', []):
            if 'seconds' in metric:
                value = f'{metric["seconds"]:g} 秒 / {metric["minutes"]:g} 分钟'
            elif 'difference_cents' in metric:
                value = f'{metric["difference_cents"] / 100:.2f} SGD 差额（未裁定退款）'
            else:
                value = f'采样路线 {metric.get("actual_sampled_length_m", 0):.1f} m / 参考 {metric.get("reference_sampled_length_m", 0):.1f} m'
            calculations.append(f'<li><b>{esc(metric["name"])}</b><span>{esc(value)}</span>{links(metric["evidence_refs"], "evidence")}</li>')
        categories = {'informational': '仅供提示', 'judge_analysis': '需 Judge 分析',
                      'requires_clarification': '必须补充政策或数据'}
        issues = ''.join(f'<li><b>{esc(categories[issue["category"]])} · {esc(issue["code"])}</b><p>{esc(issue["message"])}</p></li>'
                         for issue in review_plan(s)['items'])
        findings = ''.join(f'<li><p>{esc(f["finding"])}</p><span class="muted">{esc(f.get("finding_type", "未分类"))} · {esc(f.get("topic", "未分类"))}</span> {links(f["evidence_refs"], "evidence")} {links(f["policy_refs"], "policy")}</li>'
                           for f in ruling.get('findings', [])) or '<li>暂无可采纳的裁决依据。</li>'
        def source_cards(kind, collection):
            cards = []
            id_key, text_key = ('evidence_id', 'fact') if kind == 'evidence' else ('policy_id', 'rule')
            for item in collection:
                ref = item[id_key]
                index = s['source_index'][kind][ref]
                excerpts = [{'path': p, 'value': pointer(s['raw'], p)} for p in index['source_refs']]
                cards.append(f'<details id="{prefix}-{kind}-{esc(ref)}"><summary><b>{esc(ref)}</b> {esc(item[text_key])}</summary><p class="muted">来源：{esc(item["source"])} · 类型：{esc(index.get("kind", index.get("policy_origin", "policy")))}</p>{pretty(excerpts)}</details>')
            return ''.join(cards)
        arguments = []
        for side, label in [('rider', '乘客 Advocate'), ('driver', '司机 Advocate')]:
            rounds = []
            for round_name, title in [('opening', '第一轮陈述'), ('response', '回应对方')]:
                arg = result['arguments'][round_name].get(side)
                if not arg:
                    rounds.append(f'<h4>{title}</h4><p>未执行／输出被拒绝。</p>')
                    continue
                rows = ''.join(f'<li id="{prefix}-argument-{round_name}-{side}-{field}-{idx}">{esc(c["claim"])} {links(c["evidence_refs"], "evidence")}</li>'
                               for field in ('claims', 'counterpoints') for idx, c in enumerate(arg.get(field, [])))
                missing = ''.join(f'<li>{esc(x)}</li>' for x in arg.get('missing_information', []))
                rounds.append(f'<h4>{title}</h4><ul>{rows}</ul><ul class="muted">{missing}</ul>')
            arguments.append(f'<div><h3>{label}</h3>{"".join(rounds)}</div>')
        analysis = ruling.get('case_analysis')
        analysis_html = '<p>本次没有通过检查的结构化分析，请查看复核原因和输出检查。</p>'
        if analysis:
            assessments = {'accepted': '有依据支持', 'partly_supported': '部分有依据支持',
                           'unsupported': '依据不足', 'contradicted': '有反证', 'unresolved': '尚待判断'}
            side_cards = []
            for side, label in [('rider', '乘客观点'), ('driver', '司机观点')]:
                a = analysis['sides'][side]
                arg_links = links([ref.strip('/').replace('/', '-') for ref in a['argument_refs']], 'argument')
                side_cards.append(f'<div><h4>{label} · {esc(assessments[a["assessment"]])}</h4><p>{esc(a["reason"])}</p><p>涉及论点：{arg_links or "无"}</p><p>依据：{links(a["evidence_refs"], "evidence")} {links(a["policy_refs"], "policy")}</p></div>')
            points = ''.join(f'<li><b>{esc(x["issue"])}</b><p>{esc(x["reasoning"])}</p>{links(x["evidence_refs"], "evidence")} {links(x["policy_refs"], "policy")}</li>' for x in analysis['disputed_points'])
            responses = ''.join(f'<li><b>{esc(x["issue_code"])} · {"已处理" if x["status"] == "resolved" else "仍待澄清"}</b><p>{esc(x["explanation"])}</p>{links(x["evidence_refs"], "evidence")} {links(x["policy_refs"], "policy")}</li>' for x in analysis['review_responses'])
            missing = ''.join(f'<li>{esc(x)}</li>' for x in analysis['missing_information']) or '<li>本次分析未列出额外缺失信息。</li>'
            row_labels = {'supported': '有支持', 'partly_supported': '部分支持', 'contradicted': '有反证', 'insufficient_evidence': '缺少支持证据', 'unresolved': '尚待判断', 'not_factual_claim': '程序请求／非事实主张'}
            ledger_rows = []
            for row in analysis.get('argument_assessments', []):
                arg_link = links([row['argument_ref'].strip('/').replace('/', '-')], 'argument')
                gaps = '；'.join(row['missing_information']) or '未列出'
                ledger_rows.append(f'<li>{arg_link} <b>{esc(row_labels[row["assessment"]])}</b><p>{esc(row["reason"])}</p><p>支持记录：{links(row["supporting_evidence_refs"], "evidence") or "无"} · 反驳记录：{links(row["opposing_evidence_refs"], "evidence") or "无"}</p><p>政策：{links(row["policy_refs"], "policy") or "未引用"}</p><p class="muted">待补充：{esc(gaps)}</p></li>')
            condition_labels = {'met': '满足', 'not_met': '不满足', 'unknown': '未知'}
            conditions_html = ''.join(f'<li id="{prefix}-condition-{esc(c["condition_id"])}"><b>{esc(c["condition_id"])} · {esc(condition_labels[c["status"]])}</b><p>{esc(c["reason"])}</p>{links(c["evidence_refs"], "evidence")} {links(c["policy_refs"], "policy")}</li>' for c in analysis.get('decision_conditions', []))
            mode_note = ('当前是离线分析骨架：只列出需要判断的内容，尚未由模型评估双方观点。'
                         if result['modes']['judge'] == 'offline_review' else
                         '以下为通过结构和引用检查的分析；这些检查不能证明自然语言推理正确。')
            analysis_html = f'<p class="muted">{mode_note}</p><h4>核心问题</h4><p>{esc(analysis["question"])}</p><div class="columns">{"".join(side_cards)}</div><h4>逐条论点评估</h4><ul>{"".join(ledger_rows)}</ul><h4>裁决关键条件</h4><ul>{conditions_html}</ul><h4>争议点分析</h4><ul>{points}</ul><h4>复核问题逐项处理</h4><ul>{responses}</ul><h4>仍需补充的信息</h4><ul>{missing}</ul>'
        logs = ''.join(f'<details><summary>{e["sequence"]}. {esc(e["step"])} · {esc(e["agent"])} · {esc(e["status"])} · {e["duration_ms"]} ms</summary><p>{esc(e["started_at"])}</p>{pretty({k:v for k,v in e.items() if k in ("input", "output", "error")})}</details>' for e in result['communication_log'])
        uncertainties = ''.join(f'<li>{esc(x)}</li>' for x in ruling.get('uncertainties', []))
        notes = ''.join(f'<li>{esc(n)}</li>' for n in ruling.get('notes', []))
        provenance = result['calculations'].get('policy_provenance')
        provenance_html = ''
        if provenance:
            rows = ''.join(f'<li>{links([p["policy_id"]], "policy")} 来源：{esc(p["origin"])} · 原文路径：{esc(", ".join(p["source_refs"]))}</li>' for p in provenance['dataset_policy'])
            provenance_html = f'<section><h3>规则来源</h3><p>每条政策保留案卷中的来源标签；团队程序检查不代表平台收费政策。</p><ul>{rows}</ul><details><summary>查看团队检查约定</summary>{pretty(provenance["local_safeguards"])}</details></section>'
        lineage = result.get('supplement_lineage')
        supplement_html = ''
        if lineage:
            supplement_html = f'<section><h3>补材料后重新分析</h3><p>来源说明：{esc(lineage["source_note"])}</p><p>原结果：{esc(lineage["old_decision"])} → 新结果：{esc(lineage["new_decision"])}</p><p class="muted">双方论点按新快照重跑；来源说明未经过独立认证。</p>{pretty(lineage)}</section>'
        adjustment_html = ''
        if result.get('judge_adjustments'):
            adjustment_html = ('<section><h3>程序保守修正</h3>'
                '<p>模型对部分论点的支持评级只有当事人陈述作为依据。程序将其降为证据不足，保留原输出并重新检查全部规则；收费或退款建议未因此生成。</p>'
                '<details><summary>原始模型检查错误</summary>' + pretty(result.get('judge_raw_validation_errors', [])) + '</details>'
                '<details><summary>逐条修正记录</summary>' + pretty(result['judge_adjustments']) + '</details>'
                '<details><summary>原始 Judge 建议</summary>' + pretty(result.get('judge_proposal')) + '</details></section>')
        modes = f'Advocate: {result["modes"]["advocate"]} / Judge: {result["modes"]["judge"]}'
        panels.append(f'''<article id="{prefix}" role="tabpanel" aria-labelledby="tab-{i}" {"hidden" if i else ""}>
<div class="case-head"><div><p class="eyebrow">{esc(origin)}</p><h2>{esc(result['case_id'])}</h2></div><div class="pill">{esc(decision)}</div></div>
<p class="muted">{esc(modes)}<br>快照 {esc(s['snapshot_id'])}<br>运行 {esc(result['run_id'])}</p>
<section><h3>本次结果</h3><p>退款金额：{esc(ruling['refund_amount']) if ruling['refund_amount'] is not None else '未裁定'} SGD · 页面只展示建议，不执行收费或退款。</p><ul>{uncertainties}</ul><ul class="muted">{notes}</ul><h4>已记录的依据</h4><ul>{findings}</ul><details><summary>查看最终 JSON</summary>{pretty(ruling)}</details></section>
<section><h3>计算结果与待澄清问题</h3><p class="muted">计时口径未擅自选定；距离／差额不等于责任／退款。</p><ul class="metrics">{''.join(calculations)}</ul><ul>{issues}</ul></section>
<section><h3>Judge 如何看双方观点</h3>{analysis_html}</section>
{handoff_html}
{provenance_html}
{supplement_html}
{adjustment_html}
<section><h3>双方陈述与回应</h3><p class="muted">offline_placeholder 只摘录已有陈述，不代表已完成真实 Agent 辩论。</p><div class="columns">{''.join(arguments)}</div></section>
<section><h3>证据与原文 <span class="count">{len(s['evidence_pack']['facts'])}</span></h3><p class="muted">点击编号或展开条目查看本次快照的原始记录。</p>{source_cards('evidence',s['evidence_pack']['facts'])}</section>
<section><h3>政策与原文</h3>{source_cards('policy',s['evidence_pack']['policy'])}</section>
<section><h3>通信日志</h3>{logs}</section>
<section><h3>输出检查</h3>{pretty({'errors':result['validation_errors'],'warnings':result['validation_warnings']})}<p class="muted">格式和编号有效，不等于模型理解正确。</p></section></article>''')
    page = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>RydeResolve · Integration Review</title>
<style>
:root{color-scheme:light;--ink:#182c3a;--muted:#5f7281;--teal:#146c68}*{box-sizing:border-box}body{margin:0;background:#f1f5f5;color:var(--ink);font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:1160px;margin:0 auto;padding:36px 24px}h1{font-size:32px;margin:4px 0}h2{font-size:27px;margin:0}h3{font-size:19px;margin:0 0 12px}h4{margin:16px 0 6px}.eyebrow{color:var(--teal);font-weight:700;letter-spacing:.03em}.muted{color:var(--muted);overflow-wrap:anywhere}.banner{background:#e0eeec;border-left:4px solid var(--teal);padding:16px 20px;margin:20px 0}nav{display:flex;gap:12px;margin:24px 0}button{font:inherit;padding:10px 18px;border:1px solid #b8ccc9;border-radius:8px;cursor:pointer;background:white;color:var(--ink)}button[aria-selected=true]{background:var(--teal);color:white}section{background:#fff;border:1px solid #dbe5e6;border-radius:12px;padding:24px;margin:18px 0}.case-head{display:flex;align-items:center;justify-content:space-between;gap:16px}.pill{background:#fff0cb;color:#755600;padding:8px 16px;border-radius:22px;font-weight:700}.columns{display:grid;grid-template-columns:1fr 1fr;gap:28px}.columns>div{min-width:0}.metrics{padding-left:22px}.metrics li{margin:12px 0}.metrics span{display:block;font-size:20px}.ref{display:inline-block;padding:1px 7px;background:#e4f2ef;color:#145c58;border-radius:4px;margin:3px;text-decoration:none}.ref:hover{text-decoration:underline}details{border-top:1px solid #e0e9e9;padding:12px 0;scroll-margin-top:18px}summary{cursor:pointer;overflow-wrap:anywhere}summary b{color:var(--teal)}details:target{background:#fff7dc;padding:12px}pre{background:#f4f7f8;padding:16px;border-radius:6px;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 ui-monospace,monospace;max-height:480px;overflow:auto}li{overflow-wrap:anywhere}.count{color:var(--muted);font-size:14px}[hidden]{display:none!important}@media(max-width:700px){main{padding:20px 12px}.columns{grid-template-columns:1fr}.case-head{align-items:flex-start;flex-direction:column}section{padding:16px}h1{font-size:26px}}
</style></head><body><main><p class="eyebrow">RYDERESOLVE / TEAM INTEGRATION</p><h1>争议证据与裁决工作台</h1><div class="banner">Evidence 已接入队友 v0.2.0。运行模式见每个案件；离线结果不代表真实模型裁决。本页是一次运行的快照，切换案件不会发起模型请求。</div><nav role="tablist" aria-label="选择案件">'''+''.join(nav)+'''</nav>'''+''.join(panels)+'''</main><script>
document.querySelectorAll('[data-case]').forEach(button=>button.addEventListener('click',()=>{
document.querySelectorAll('[data-case]').forEach(b=>b.setAttribute('aria-selected',String(b===button)));
document.querySelectorAll('[role=tabpanel]').forEach(p=>p.hidden=p.id!==button.dataset.case);
}));
document.querySelectorAll('a.ref').forEach(link=>link.addEventListener('click',()=>{const target=document.getElementById(link.hash.slice(1));if(target)target.open=true;}));
</script></body></html>'''
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding='utf-8')
    return path
